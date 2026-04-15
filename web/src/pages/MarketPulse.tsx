import { useEffect, useState } from 'react'
import { Zap, Search } from 'lucide-react'
import * as api from '../api'
import type { WsMessage } from '../useWebSocket'

interface Props {
  ws: { messages: WsMessage[]; connected: boolean }
}

export default function MarketPulse({ ws }: Props) {
  const [query, setQuery] = useState('')
  const [insight, setInsight] = useState('')
  const [loading, setLoading] = useState(false)
  const [decisions, setDecisions] = useState<any[]>([])

  useEffect(() => {
    api.getDecisions(20).then(setDecisions).catch(() => {})
    const t = setInterval(() => api.getDecisions(20).then(setDecisions).catch(() => {}), 20000)
    return () => clearInterval(t)
  }, [])

  const handleAsk = async () => {
    if (!query.trim()) return
    setLoading(true)
    try {
      const res = await api.askSage(query)
      setInsight(res.answer || res.error || JSON.stringify(res))
    } catch (e: any) {
      setInsight(`Error: ${e.message}`)
    }
    setLoading(false)
  }

  // Split signals from WS
  const signals = ws.messages.filter(m => m.type === 'signal' || m.type === 'decision')
  const events = ws.messages.filter(m => m.type !== 'signal' && m.type !== 'decision')

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr 320px', gap: 'var(--sp-5)', height: 'calc(100vh - 100px)' }}>
      {/* ── Left: Live Pulse ─────────────────────────────────── */}
      <div className="card" style={{ overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', marginBottom: 'var(--sp-4)' }}>
          <div className="pulse-dot" />
          <span className="text-display" style={{ fontSize: '0.8rem', letterSpacing: '0.1em' }}>
            LIVE PULSE
          </span>
          <span className="chip chip-green" style={{ marginLeft: 'auto', fontSize: '0.6rem' }}>Real-Time</span>
        </div>
        <div style={{ flex: 1, overflow: 'auto' }}>
          {events.length === 0 && (
            <div style={{ color: 'var(--outline)', fontSize: '0.75rem', padding: 'var(--sp-3)' }}>
              Waiting for market events...
            </div>
          )}
          {events.slice(0, 40).map((ev, i) => (
            <div key={i} className={`feed-item animate-in ${getEventColor(ev)}`} style={{ marginBottom: 2 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontWeight: 600, fontSize: '0.75rem' }}>
                  {ev.token || ev.type.replace(/_/g, ' ')}
                </span>
                <span className={`chip ${getEventChip(ev)}`} style={{ fontSize: '0.55rem' }}>
                  {formatType(ev.type)}
                </span>
              </div>
              {ev.reasoning && (
                <div style={{ fontSize: '0.7rem', color: 'var(--on-surface-variant)', marginTop: 2 }}>
                  {ev.reasoning.slice(0, 80)}
                </div>
              )}
              {ev.amount_usd && (
                <div className="text-mono" style={{ fontSize: '0.7rem', color: 'var(--outline)' }}>
                  ${Number(ev.amount_usd).toLocaleString()}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── Center: Token Detail + Insight ───────────────────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-5)', overflow: 'auto' }}>
        {/* Latest decision detail */}
        {decisions[0] && (
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-4)', marginBottom: 'var(--sp-4)' }}>
              <div style={{
                width: 48, height: 48, borderRadius: 'var(--radius-lg)',
                background: 'var(--surface-container)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Zap size={24} color="var(--primary)" />
              </div>
              <div>
                <div className="text-display" style={{ fontSize: '1.4rem' }}>
                  {decisions[0].token}
                  <span className="chip chip-neutral" style={{ marginLeft: 'var(--sp-2)', fontSize: '0.6rem', verticalAlign: 'middle' }}>
                    {decisions[0].signal_type?.replace(/_/g, ' ') || 'signal'}
                  </span>
                </div>
                <div className="text-mono" style={{ color: 'var(--on-surface-variant)', fontSize: '0.8rem' }}>
                  {decisions[0].chain}
                </div>
              </div>
            </div>

            {/* Stats grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--sp-3)', marginBottom: 'var(--sp-4)' }}>
              <MiniStat label="Action" value={decisions[0].action} color={decisions[0].action === 'buy' ? 'var(--primary)' : decisions[0].action === 'sell' ? 'var(--tertiary)' : 'var(--outline)'} />
              <MiniStat label="Confidence" value={`${(decisions[0].confidence * 100).toFixed(0)}%`} color="var(--secondary)" />
              <MiniStat label="Amount" value={`$${decisions[0].amount_usd?.toFixed(2)}`} color="var(--on-surface)" />
              <MiniStat label="Chain" value={decisions[0].chain} color="var(--on-surface-variant)" />
            </div>
          </div>
        )}

        {/* SAGE Insight box */}
        <div className="glass" style={{ borderRadius: 'var(--radius-lg)', padding: 'var(--sp-5)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', marginBottom: 'var(--sp-3)' }}>
            <Zap size={16} color="var(--secondary)" />
            <span className="text-display" style={{ fontSize: '0.8rem', color: 'var(--secondary)' }}>
              SAGE INSIGHT
            </span>
          </div>
          <div style={{ fontSize: '0.85rem', lineHeight: 1.6, color: 'var(--on-surface-variant)' }}>
            {insight || (decisions[0]?.reasoning) || 'Ask SAGE about any token or market event to see intelligence here.'}
          </div>
        </div>

        {/* Ask bar */}
        <div style={{ display: 'flex', gap: 'var(--sp-2)', alignItems: 'center', background: 'var(--surface-low)', borderRadius: 'var(--radius-lg)', padding: 'var(--sp-2) var(--sp-4)' }}>
          <Search size={18} color="var(--outline)" />
          <input
            className="input"
            style={{ border: 'none', background: 'transparent', flex: 1 }}
            placeholder="Ask SAGE about any token or market event..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleAsk()}
          />
          <button className="btn-primary" onClick={handleAsk} disabled={loading}
            style={{ padding: '6px 16px', fontSize: '0.75rem', opacity: loading ? 0.5 : 1 }}>
            {loading ? '...' : '→'}
          </button>
        </div>
      </div>

      {/* ── Right: Signal Detector ───────────────────────────── */}
      <div className="card" style={{ overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
        <div className="text-display" style={{ fontSize: '0.8rem', letterSpacing: '0.1em', marginBottom: 'var(--sp-4)' }}>
          SIGNAL DETECTOR
        </div>
        {signals.length === 0 && decisions.length === 0 && (
          <div style={{ color: 'var(--outline)', fontSize: '0.75rem', padding: 'var(--sp-3)' }}>
            No signals detected yet.
          </div>
        )}
        {[...signals.slice(0, 10), ...decisions.slice(0, 10)].map((s: any, i: number) => (
          <div key={i} className="feed-item animate-in" style={{
            marginBottom: 'var(--sp-2)',
            borderLeftColor: s.action === 'buy' ? 'var(--primary)' : s.action === 'sell' ? 'var(--tertiary)' : 'var(--secondary)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="text-display" style={{ fontSize: '0.75rem', color: getSignalColor(s) }}>
                {s.signal_type?.replace(/_/g, ' ').toUpperCase() || s.type?.replace(/_/g, ' ').toUpperCase()}
              </span>
              <span style={{ fontSize: '0.6rem', color: 'var(--outline)' }}>
                {s.timestamp ? new Date(s.timestamp * 1000).toLocaleTimeString() : 'now'}
              </span>
            </div>
            <div style={{ fontWeight: 600, fontSize: '0.8rem', marginTop: 2 }}>{s.token}</div>
            {s.reasoning && (
              <div style={{ fontSize: '0.7rem', color: 'var(--on-surface-variant)', marginTop: 2 }}>
                {s.reasoning.slice(0, 100)}
              </div>
            )}
            {s.confidence !== undefined && (
              <div style={{ fontSize: '0.65rem', color: 'var(--secondary)', marginTop: 2 }}>
                Confidence: {(s.confidence * 100).toFixed(0)}%
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function MiniStat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="card-inset" style={{ textAlign: 'center', padding: 'var(--sp-3)' }}>
      <div className="stat-label" style={{ fontSize: '0.6rem', marginBottom: 4 }}>{label}</div>
      <div className="text-mono" style={{ fontSize: '1rem', fontWeight: 700, color }}>{value}</div>
    </div>
  )
}

function getEventColor(ev: WsMessage) {
  if (ev.type.includes('trade')) return 'feed-item--green'
  if (ev.type.includes('block') || ev.type.includes('error')) return 'feed-item--red'
  return ''
}

function getEventChip(ev: WsMessage) {
  if (ev.type.includes('trade')) return 'chip-green'
  if (ev.type.includes('close') || ev.type.includes('block')) return 'chip-red'
  return 'chip-purple'
}

function formatType(t: string) {
  return t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function getSignalColor(s: any) {
  if (s.action === 'buy') return 'var(--primary)'
  if (s.action === 'sell' || s.type?.includes('rug')) return 'var(--tertiary)'
  return 'var(--secondary)'
}

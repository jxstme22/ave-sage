import { useEffect, useState } from 'react'
import { Activity, Database, Brain, TrendingUp, Zap, AlertTriangle } from 'lucide-react'
import * as api from '../api'
import type { WsMessage } from '../useWebSocket'

interface Props {
  ws: { messages: WsMessage[]; connected: boolean }
}

export default function CommandCenter({ ws }: Props) {
  const [health, setHealth] = useState<any>(null)
  const [stats, setStats] = useState<any>(null)
  const [rules, setRules] = useState<any>(null)
  const [decisions, setDecisions] = useState<any[]>([])
  const [positions, setPositions] = useState<any[]>([])

  useEffect(() => {
    const load = () => {
      api.getHealth().then(setHealth).catch(() => {})
      api.getMemoryStats().then(setStats).catch(() => {})
      api.getRulesStatus().then(setRules).catch(() => {})
      api.getDecisions(5).then(setDecisions).catch(() => {})
      api.getOpenPositions().then(setPositions).catch(() => {})
    }
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-6)' }}>
      {/* ── Stats Row ────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--sp-4)' }}>
        <StatCard icon={<Database size={16} />} label="Memory Chunks"
          value={stats?.total_chunks?.toLocaleString() ?? '—'}
          sub={health?.status === 'ok' ? '● Operational' : '● Loading...'} color="var(--primary)" />
        <StatCard icon={<Zap size={16} />} label="Signals Detected"
          value={String(decisions.length ?? 0)}
          sub="Last 5 decisions" color="var(--secondary)" />
        <StatCard icon={<TrendingUp size={16} />} label="Open Positions"
          value={String(positions.length ?? 0)}
          sub={`${ws.connected ? 'Live' : 'Offline'} monitoring`} color="var(--primary)" />
        <StatCard icon={<AlertTriangle size={16} />} label="Daily P&L"
          value={rules ? `$${rules.daily_pnl_usd?.toFixed(2) ?? '0.00'}` : '—'}
          sub={rules?.halted ? '🛑 Halted' : '✅ Active'} color={rules?.daily_pnl_usd < 0 ? 'var(--tertiary)' : 'var(--primary)'} />
      </div>

      {/* ── Two columns: Live Feed + Recent Decisions ────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-5)' }}>
        {/* Live Feed */}
        <div className="card" style={{ maxHeight: 480, overflow: 'auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', marginBottom: 'var(--sp-4)' }}>
            <div className="pulse-dot" />
            <span className="text-display" style={{ fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              Live Pulse
            </span>
            <span style={{ marginLeft: 'auto', fontSize: '0.65rem' }} className="chip chip-green">Real-Time</span>
          </div>
          {ws.messages.length === 0 && (
            <div style={{ color: 'var(--outline)', fontSize: '0.8rem', padding: 'var(--sp-4)' }}>
              Waiting for events...
            </div>
          )}
          {ws.messages.slice(0, 50).map((msg, i) => (
            <div key={i} className={`feed-item animate-in ${getFeedColor(msg.type)}`}
              style={{ marginBottom: 2 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 600 }}>
                  {msg.token || msg.type.replace(/_/g, ' ').toUpperCase()}
                </span>
                <span className={`chip ${getChipClass(msg.type)}`} style={{ fontSize: '0.6rem' }}>
                  {msg.type.replace(/_/g, ' ')}
                </span>
              </div>
              {msg.reasoning && (
                <div style={{ fontSize: '0.7rem', color: 'var(--on-surface-variant)', marginTop: 2 }}>
                  {msg.reasoning.slice(0, 120)}
                </div>
              )}
              {msg.pnl_pct !== undefined && (
                <div className="text-mono" style={{ fontSize: '0.75rem', color: msg.pnl_pct >= 0 ? 'var(--primary)' : 'var(--tertiary)' }}>
                  PnL: {msg.pnl_pct > 0 ? '+' : ''}{msg.pnl_pct}%
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Recent Decisions */}
        <div className="card" style={{ maxHeight: 480, overflow: 'auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', marginBottom: 'var(--sp-4)' }}>
            <Brain size={16} color="var(--secondary)" />
            <span className="text-display" style={{ fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              Recent Decisions
            </span>
          </div>
          {decisions.length === 0 && (
            <div style={{ color: 'var(--outline)', fontSize: '0.8rem', padding: 'var(--sp-4)' }}>
              No decisions yet.
            </div>
          )}
          {decisions.map((d: any, i: number) => (
            <div key={i} className="feed-item" style={{ marginBottom: 'var(--sp-2)', borderLeftColor: getActionColor(d.action) }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 600, fontSize: '0.8rem' }}>{d.token}</span>
                <span className={`chip ${d.action === 'buy' ? 'chip-green' : d.action === 'sell' ? 'chip-red' : 'chip-neutral'}`}>
                  {d.action}
                </span>
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--on-surface-variant)', marginTop: 2 }}>
                {d.reasoning?.slice(0, 100)}
              </div>
              <div style={{ display: 'flex', gap: 'var(--sp-4)', marginTop: 4, fontSize: '0.7rem', color: 'var(--outline)' }}>
                <span>Conf: <span className="text-mono" style={{ color: 'var(--secondary)' }}>
                  {(d.confidence * 100).toFixed(0)}%</span>
                </span>
                <span>${d.amount_usd?.toFixed(2)}</span>
                <span className="chip chip-neutral" style={{ fontSize: '0.55rem' }}>{d.chain}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Open Positions ───────────────────────────────────── */}
      {positions.length > 0 && (
        <div className="card">
          <div className="text-display" style={{ fontSize: '0.8rem', marginBottom: 'var(--sp-4)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
            Open Positions
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--sp-3)' }}>
            {positions.map((p: any, i: number) => (
              <div key={i} className="card-inset" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 600 }}>{p.token}</span>
                  <span className={`chip ${p.pnl_pct >= 0 ? 'chip-green' : 'chip-red'}`}>
                    {p.pnl_pct > 0 ? '+' : ''}{p.pnl_pct}%
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 'var(--sp-4)', fontSize: '0.7rem', color: 'var(--outline)' }}>
                  <span>Entry: <span className="text-mono">${p.entry?.toFixed(6)}</span></span>
                  <span>Current: <span className="text-mono">${p.current?.toFixed(6)}</span></span>
                </div>
                <div style={{ display: 'flex', gap: 'var(--sp-3)', fontSize: '0.65rem' }}>
                  <span className="chip chip-neutral">{p.chain}</span>
                  <span className="chip chip-neutral">{p.action}</span>
                  <span style={{ color: 'var(--outline)' }}>${p.amount_usd?.toFixed(2)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({ icon, label, value, sub, color }: {
  icon: React.ReactNode; label: string; value: string; sub: string; color: string
}) {
  return (
    <div className="stat-card">
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
        <span style={{ color }}>{icon}</span>
        <span className="stat-label">{label}</span>
      </div>
      <div className="stat-value" style={{ color }}>{value}</div>
      <div className="stat-sub">{sub}</div>
    </div>
  )
}

function getFeedColor(type: string) {
  if (type.includes('trade') || type.includes('opened')) return 'feed-item--green'
  if (type.includes('blocked') || type.includes('closed')) return 'feed-item--red'
  if (type.includes('decision') || type.includes('signal')) return 'feed-item--purple'
  return ''
}

function getChipClass(type: string) {
  if (type.includes('trade')) return 'chip-green'
  if (type.includes('blocked') || type.includes('error')) return 'chip-red'
  return 'chip-purple'
}

function getActionColor(action: string) {
  if (action === 'buy') return 'var(--primary)'
  if (action === 'sell') return 'var(--tertiary)'
  return 'var(--outline-variant)'
}

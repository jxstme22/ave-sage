import { useState } from 'react'
import { ArrowDownUp, Lightbulb } from 'lucide-react'
import * as api from '../api'

export default function SwapPage() {
  const [fromAmount, setFromAmount] = useState('10.0')
  const [insight, setInsight] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSwap = async () => {
    setInsight('')
    setLoading(true)
    try {
      const res = await api.askSage(`Should I swap ${fromAmount} SOL to USDT right now? Give a brief recommendation.`)
      setInsight(res.answer || res.response || JSON.stringify(res))
    } catch (e: any) {
      setInsight(`Error: ${e.message}`)
    }
    setLoading(false)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)', paddingTop: 'var(--sp-3)' }}>

      {/* ── Card ────────────────────────────────────────────────── */}
      <div className="card" style={{ position: 'relative', overflow: 'hidden', display: 'flex', flexDirection: 'column', gap: 'var(--sp-3)' }}>
        {/* Glow */}
        <div style={{ position: 'absolute', top: -30, right: -30, width: 80, height: 80, background: 'radial-gradient(circle, rgba(68,224,146,0.07), transparent)', borderRadius: '50%', pointerEvents: 'none' }} />

        <div className="section-header" style={{ position: 'relative', zIndex: 1 }}>
          <span className="section-title">SAGE Swap</span>
          <span className="chip chip-green">AI Insight</span>
        </div>

        {/* From */}
        <div className="card-inset" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 9, color: 'var(--outline)', textTransform: 'uppercase', fontWeight: 700, marginBottom: 3, letterSpacing: '0.1em' }}>You Pay</div>
            <input
              type="text"
              value={fromAmount}
              onChange={e => setFromAmount(e.target.value)}
              style={{
                background: 'transparent', border: 'none', color: 'var(--on-surface)',
                fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.2rem',
                outline: 'none', width: 110,
              }}
            />
          </div>
          <TokenBadge name="SOL" gradient="linear-gradient(135deg, #9945FF, #14F195)" />
        </div>

        {/* Swap icon */}
        <div style={{ display: 'flex', justifyContent: 'center', margin: '-4px 0', zIndex: 2 }}>
          <div style={{
            background: 'var(--surface-container)', color: 'var(--primary)',
            padding: 5, borderRadius: 'var(--radius-md)',
            border: '2px solid var(--surface-lowest)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <ArrowDownUp size={13} />
          </div>
        </div>

        {/* To */}
        <div className="card-inset" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 9, color: 'var(--outline)', textTransform: 'uppercase', fontWeight: 700, marginBottom: 3, letterSpacing: '0.1em' }}>SAGE Recommends</div>
            <span className="text-display" style={{ fontSize: '1.1rem', color: 'var(--on-surface-variant)' }}>—</span>
          </div>
          <TokenBadge name="USDT" color="#26A17B" />
        </div>

        {/* Insight */}
        {insight && (
          <div style={{
            background: 'rgba(68,224,146,0.07)', borderRadius: 'var(--radius-md)',
            padding: 'var(--sp-3)', display: 'flex', alignItems: 'flex-start', gap: 8,
            border: '1px solid rgba(68,224,146,0.15)',
          }}>
            <Lightbulb size={13} color="var(--primary)" style={{ flexShrink: 0, marginTop: 1 }} />
            <p style={{ fontSize: 11, lineHeight: 1.45, color: 'var(--on-surface)' }}>{insight}</p>
          </div>
        )}

        <button
          className="btn-primary"
          onClick={handleSwap}
          disabled={loading}
          style={{ width: '100%', padding: '12px', fontSize: 11 }}
        >
          {loading ? 'Analyzing…' : 'Ask SAGE'}
        </button>
      </div>

      {/* ── Disclaimer ──────────────────────────────────────────── */}
      <p style={{ fontSize: 9.5, color: 'var(--outline)', textAlign: 'center', lineHeight: 1.5, padding: '0 var(--sp-2)' }}>
        SAGE provides AI-generated market insights. Always verify before executing trades.
      </p>
    </div>
  )
}

function TokenBadge({ name, gradient, color }: { name: string; gradient?: string; color?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, background: 'var(--surface-high)', padding: '5px 10px', borderRadius: 'var(--radius-md)', border: '1px solid rgba(255,255,255,0.05)' }}>
      <div style={{ width: 18, height: 18, borderRadius: '50%', background: gradient ?? color ?? 'var(--outline)' }} />
      <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-display)' }}>{name}</span>
    </div>
  )
}

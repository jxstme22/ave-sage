import { useEffect, useState } from 'react'
import * as api from '../api'

export default function SignalsPage() {
  const [decisions, setDecisions] = useState<any[]>([])
  const [rules, setRules] = useState<any>(null)

  useEffect(() => {
    const load = () => {
      api.getDecisions(15).then(setDecisions).catch(() => {})
      api.getRulesStatus().then(setRules).catch(() => {})
    }
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [])

  const buys  = decisions.filter(d => d.action === 'buy').length
  const sells = decisions.filter(d => d.action === 'sell').length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)', paddingTop: 'var(--sp-3)' }}>

      {/* ── Stats row ───────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
        <StatCard label="Signals" value={String(decisions.length)} color="var(--primary)" />
        <StatCard label="Buys" value={String(buys)} color="var(--primary)" />
        <StatCard label="Sells" value={String(sells)} color="var(--tertiary)" />
        <StatCard
          label="Status"
          value={rules?.halted ? 'HALTED' : 'Active'}
          color={rules?.halted ? 'var(--tertiary)' : 'var(--primary)'}
        />
      </div>

      {/* ── Signal list ─────────────────────────────────────────── */}
      <div>
        <div className="section-header">
          <span className="section-title">Signal History</span>
          {rules?.open_positions != null && (
            <span className="chip chip-green">{rules.open_positions} open</span>
          )}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
          {decisions.length === 0 && (
            <div style={{ fontSize: 11, color: 'var(--outline)', padding: 'var(--sp-3) 0' }}>
              No signals detected yet.
            </div>
          )}
          {decisions.map((d, i) => (
            <div key={i} className={`feed-item animate-in feed-item--${d.action === 'buy' ? 'green' : d.action === 'sell' ? 'red' : 'purple'}`}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontWeight: 700, fontSize: 13, fontFamily: 'var(--font-display)' }}>{d.token}</span>
                  <span className={`chip ${d.action === 'buy' ? 'chip-green' : d.action === 'sell' ? 'chip-red' : 'chip-purple'}`}>
                    {d.action}
                  </span>
                </div>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--on-surface-variant)' }}>
                  {d.confidence != null ? `${(d.confidence * 100).toFixed(0)}%` : ''}
                  {d.amount_usd ? ` · $${d.amount_usd.toFixed(2)}` : ''}
                </span>
              </div>
              <div style={{ fontSize: 10.5, color: 'var(--on-surface-variant)', lineHeight: 1.4, marginTop: 3 }}>
                {d.signal_type?.replace(/_/g, ' ') || 'Signal'} · {d.chain}
                {d.executed ? ' · ✓ executed' : ''}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="stat-card" style={{ flex: 1, alignItems: 'center' }}>
      <div className="stat-label">{label}</div>
      <div className="text-mono" style={{ fontSize: '1.1rem', fontWeight: 700, color }}>{value}</div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { ShieldCheck, AlertTriangle, RefreshCw } from 'lucide-react'
import * as api from '../api'

export default function RiskAssessment() {
  const [rules, setRules] = useState<any>(null)
  const [ledger, setLedger] = useState<any[]>([])
  const [tuned, setTuned] = useState<any[]>([])
  const [tuning, setTuning] = useState(false)

  useEffect(() => {
    api.getRulesStatus().then(setRules).catch(() => {})
    api.getStrategyLedger().then(d => setLedger(Array.isArray(d) ? d : [])).catch(() => {})
    api.getStrategyTune().then(d => setTuned(Array.isArray(d) ? d : [])).catch(() => {})
  }, [])

  const reTune = async () => {
    setTuning(true)
    try {
      const d = await api.getStrategyTune()
      setTuned(Array.isArray(d) ? d : [])
    } catch {}
    setTuning(false)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-5)' }}>
      {/* ── Rules Engine Status ──────────────────────────────── */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)', marginBottom: 'var(--sp-5)' }}>
          <ShieldCheck size={20} color="var(--primary)" />
          <span className="text-display" style={{ fontSize: '1rem' }}>Trading Rules Engine</span>
          {rules && (
            <span className={`chip ${rules.halted ? 'chip-red' : 'chip-green'}`} style={{ marginLeft: 'auto' }}>
              {rules.halted ? '🛑 HALTED' : '✅ Active'}
            </span>
          )}
        </div>

        {rules ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--sp-4)' }}>
            <RuleCard label="Daily P&L"
              value={`$${rules.daily_pnl_usd?.toFixed(2)}`}
              limit={`Limit: $${rules.max_daily_loss_usd?.toFixed(0)}`}
              pct={Math.min(Math.abs(rules.daily_pnl_usd || 0) / (rules.max_daily_loss_usd || 100), 1)}
              danger={rules.daily_pnl_usd < 0} />
            <RuleCard label="Drawdown"
              value={`${(rules.drawdown_pct || 0).toFixed(1)}%`}
              limit={`Max: ${((rules.max_drawdown_pct || 0.15) * 100).toFixed(0)}%`}
              pct={Math.min((rules.drawdown_pct || 0) / ((rules.max_drawdown_pct || 0.15) * 100), 1)}
              danger={(rules.drawdown_pct || 0) > 10} />
            <RuleCard label="Concurrent Positions"
              value={`${rules.open_positions || 0}`}
              limit={`Max: ${rules.max_concurrent || 5}`}
              pct={(rules.open_positions || 0) / (rules.max_concurrent || 5)}
              danger={(rules.open_positions || 0) >= (rules.max_concurrent || 5)} />
            <RuleCard label="Cooldown"
              value={rules.cooldown_remaining_s > 0 ? `${rules.cooldown_remaining_s}s` : 'Clear'}
              limit={`After loss: ${rules.cooldown_seconds || 300}s`}
              pct={rules.cooldown_remaining_s > 0 ? rules.cooldown_remaining_s / (rules.cooldown_seconds || 300) : 0}
              danger={rules.cooldown_remaining_s > 0} />
            <RuleCard label="Min Liquidity"
              value={`$${(rules.min_liquidity_usd || 10000).toLocaleString()}`}
              limit="Per-trade floor"
              pct={0} danger={false} />
            <RuleCard label="Max Risk Score"
              value={`${(rules.max_risk_score || 0.65).toFixed(2)}`}
              limit="Per-token limit"
              pct={0} danger={false} />
          </div>
        ) : (
          <div style={{ color: 'var(--outline)', fontSize: '0.8rem' }}>Loading rules status...</div>
        )}
      </div>

      {/* ── Strategy Ledger ──────────────────────────────────── */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)', marginBottom: 'var(--sp-4)' }}>
          <AlertTriangle size={18} color="var(--secondary)" />
          <span className="text-display" style={{ fontSize: '0.9rem' }}>Strategy Performance Ledger</span>
        </div>

        {ledger.length === 0 ? (
          <div style={{ color: 'var(--outline)', fontSize: '0.8rem' }}>No strategy records yet. Trades will appear here as they close.</div>
        ) : (
          <>
            {/* Header */}
            <div style={{
              display: 'grid', gridTemplateColumns: '1fr 80px 80px 80px 80px 90px',
              gap: 'var(--sp-2)', padding: 'var(--sp-2) var(--sp-3)',
              background: 'var(--surface-container)', borderRadius: 'var(--radius-sm)', marginBottom: 'var(--sp-2)',
            }}>
              {['Signal Type', 'Chain', 'Trades', 'Win Rate', 'Total P&L', 'Size Mult'].map(h => (
                <span key={h} className="stat-label" style={{ fontSize: '0.6rem' }}>{h}</span>
              ))}
            </div>
            {ledger.map((r: any, i: number) => (
              <div key={i} style={{
                display: 'grid', gridTemplateColumns: '1fr 80px 80px 80px 80px 90px',
                gap: 'var(--sp-2)', padding: 'var(--sp-3)',
                background: i % 2 === 0 ? 'transparent' : 'var(--surface-lowest)',
                borderRadius: 'var(--radius-sm)',
              }}>
                <span style={{ fontWeight: 600, fontSize: '0.8rem' }}>
                  {r.signal_type?.replace(/_/g, ' ')}
                </span>
                <span className="chip chip-neutral" style={{ fontSize: '0.55rem', justifySelf: 'start' }}>
                  {(r.chain || '').toUpperCase()}
                </span>
                <span className="text-mono" style={{ fontSize: '0.75rem' }}>{r.total_trades}</span>
                <span className="text-mono" style={{
                  fontSize: '0.75rem',
                  color: (r.win_rate || 0) >= 0.5 ? 'var(--primary)' : 'var(--tertiary)',
                }}>
                  {((r.win_rate || 0) * 100).toFixed(0)}%
                </span>
                <span className="text-mono" style={{
                  fontSize: '0.75rem',
                  color: (r.total_pnl_pct || 0) >= 0 ? 'var(--primary)' : 'var(--tertiary)',
                }}>
                  {r.total_pnl_pct > 0 ? '+' : ''}{(r.total_pnl_pct || 0).toFixed(1)}%
                </span>
                <span className="text-mono" style={{ fontSize: '0.75rem' }}>
                  ×{(r.tuned_size_multiplier || 1.0).toFixed(1)}
                </span>
              </div>
            ))}
          </>
        )}
      </div>

      {/* ── Self-Tuned Parameters ────────────────────────────── */}
      <div className="glass" style={{ borderRadius: 'var(--radius-lg)', padding: 'var(--sp-5)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)', marginBottom: 'var(--sp-4)' }}>
          <RefreshCw size={16} color="var(--secondary)" />
          <span className="text-display" style={{ fontSize: '0.8rem', color: 'var(--secondary)' }}>
            Self-Tuned Parameters
          </span>
          <button className="btn-ghost" onClick={reTune} disabled={tuning}
            style={{ marginLeft: 'auto', fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: 4 }}>
            <RefreshCw size={12} className={tuning ? 'spin' : ''} /> Re-Tune
          </button>
        </div>

        {tuned.filter(t => t.source === 'tuned').length === 0 ? (
          <div style={{ color: 'var(--outline)', fontSize: '0.8rem' }}>
            No strategies tuned yet (need ≥5 trades per signal type).
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--sp-3)' }}>
            {tuned.filter(t => t.source === 'tuned').map((t: any, i: number) => (
              <div key={i} className="card-inset">
                <div style={{ fontWeight: 600, fontSize: '0.8rem', marginBottom: 'var(--sp-2)' }}>
                  {t.signal_type?.replace(/_/g, ' ')}
                  <span className="chip chip-neutral" style={{ fontSize: '0.5rem', marginLeft: 'var(--sp-2)' }}>
                    {t.chain}
                  </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 'var(--sp-2)', fontSize: '0.7rem' }}>
                  <div>TP: <span className="text-mono" style={{ color: 'var(--primary)' }}>{(t.tp_pct * 100).toFixed(1)}%</span></div>
                  <div>SL: <span className="text-mono" style={{ color: 'var(--tertiary)' }}>{(t.sl_pct * 100).toFixed(1)}%</span></div>
                  <div>Conf ≥ <span className="text-mono" style={{ color: 'var(--secondary)' }}>{t.confidence_min?.toFixed(2)}</span></div>
                  <div>Size ×<span className="text-mono" style={{ color: 'var(--on-surface)' }}>{t.size_multiplier?.toFixed(1)}</span></div>
                </div>
                <div style={{ fontSize: '0.65rem', color: 'var(--outline)', marginTop: 'var(--sp-2)' }}>
                  WR: {(t.win_rate * 100).toFixed(0)}% | {t.sample_count} trades
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function RuleCard({ label, value, limit, pct, danger }: {
  label: string; value: string; limit: string; pct: number; danger: boolean
}) {
  return (
    <div className="card-inset" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
      <span className="stat-label" style={{ fontSize: '0.6rem' }}>{label}</span>
      <span className="text-mono" style={{
        fontSize: '1.1rem', fontWeight: 700,
        color: danger ? 'var(--tertiary)' : 'var(--on-surface)',
      }}>{value}</span>
      {pct > 0 && (
        <div className="progress-bar">
          <div className="progress-fill" style={{
            width: `${Math.min(pct * 100, 100)}%`,
            background: danger ? 'var(--tertiary)' : 'var(--primary)',
          }} />
        </div>
      )}
      <span style={{ fontSize: '0.6rem', color: 'var(--outline)' }}>{limit}</span>
    </div>
  )
}

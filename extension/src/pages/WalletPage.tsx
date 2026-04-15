import { useEffect, useState } from 'react'
import { Copy, Check } from 'lucide-react'
import * as api from '../api'

export default function WalletPage() {
  const [positions, setPositions] = useState<any[]>([])
  const [holdings, setHoldings] = useState<any[]>([])
  const [decisions, setDecisions] = useState<any[]>([])
  const [wallet, setWallet] = useState<any>(null)

  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const load = () => {
      api.getOpenPositions().then(setPositions).catch(() => {})
      api.getWalletHoldings().then((h: any) => setHoldings(h?.holdings || [])).catch(() => {})
      api.getDecisions(5).then(setDecisions).catch(() => {})
      api.getWalletBalance().then(setWallet).catch(() => {})
    }
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [])

  const totalValue = positions.reduce((s, p) => s + (p.amount_usd || 0), 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)', paddingTop: 'var(--sp-3)', paddingBottom: 'var(--sp-2)' }}>

      {/* ── Wallet card ─────────────────────────────────────────── */}
      <div className="card" style={{ position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: -24, right: -24, width: 80, height: 80, background: 'radial-gradient(circle, rgba(68,224,146,0.08), transparent)', borderRadius: '50%' }} />
        <div className="stat-label" style={{ marginBottom: 4 }}>Wallet Balance</div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span className="text-display" style={{ fontSize: '1.75rem', color: wallet?.sol_balance != null ? 'var(--on-surface)' : 'var(--outline)' }}>
            {wallet?.sol_balance != null ? `${wallet.sol_balance}` : '—'}
          </span>
          {wallet?.sol_balance != null && (
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--primary)', fontFamily: 'var(--font-mono)' }}>SOL</span>
          )}
          {wallet?.wallet_name && (
            <span className="chip chip-purple" style={{ marginLeft: 4 }}>{wallet.wallet_name}</span>
          )}
        </div>
        {wallet?.address && (
          <div style={{ fontSize: 9.5, color: 'var(--outline)', fontFamily: 'var(--font-mono)', marginTop: 4, letterSpacing: '0.03em', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}
            onClick={() => { navigator.clipboard.writeText(wallet.address); setCopied(true); setTimeout(() => setCopied(false), 1500) }}
            title="Copy wallet address">
            {wallet.address.slice(0, 10)}…{wallet.address.slice(-6)}
            {copied ? <Check size={10} color="var(--primary)" /> : <Copy size={10} />}
          </div>
        )}
      </div>

      {/* ── Positions ───────────────────────────────────────────── */}
      {positions.length > 0 && (
        <div>
          <div className="section-header">
            <span className="section-title">Open Positions</span>
            <span className="chip chip-green">{positions.length} open · ${totalValue.toFixed(2)}</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
            {positions.map((p, i) => {
              const pnl = p.pnl_pct ?? 0
              const pnlColor = pnl > 0 ? 'var(--primary)' : pnl < 0 ? 'var(--tertiary)' : 'var(--outline)'
              return (
                <div key={i} className="feed-item animate-in feed-item--green" style={{
                  borderLeftColor: pnl > 0 ? 'var(--primary)' : pnl < 0 ? 'var(--tertiary)' : 'var(--outline-variant)',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontWeight: 700, fontSize: 13, fontFamily: 'var(--font-display)' }}>{p.token}</span>
                      <span className={`chip ${pnl > 0 ? 'chip-green' : pnl < 0 ? 'chip-red' : 'chip-neutral'}`}>
                        {pnl > 0 ? '+' : ''}{pnl.toFixed(2)}%
                      </span>
                    </div>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--on-surface-variant)' }}>
                      ${p.amount_usd?.toFixed(2) ?? '—'}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 3 }}>
                    <span style={{ fontSize: 10, color: 'var(--outline)', fontFamily: 'var(--font-mono)' }}>
                      {p.chain} · Entry ${p.entry > 0 ? p.entry.toPrecision(5) : '—'}
                    </span>
                    <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: pnlColor }}>
                      Now ${p.current > 0 ? p.current.toPrecision(5) : '—'}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Token Holdings ──────────────────────────────────────── */}
      {holdings.length > 0 && (
        <div>
          <div className="section-header">
            <span className="section-title">Token Holdings</span>
            <span className="chip chip-purple">{holdings.length} tokens</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
            {holdings.map((h, i) => (
              <div key={i} className="feed-item animate-in feed-item--green">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 700, fontSize: 12, fontFamily: 'var(--font-mono)' }}>
                    {h.mint?.slice(0, 6)}…{h.mint?.slice(-4)}
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600, color: 'var(--primary)' }}>
                    {h.amount >= 1e9 ? `${(h.amount / 1e9).toFixed(2)}B`
                      : h.amount >= 1e6 ? `${(h.amount / 1e6).toFixed(2)}M`
                      : h.amount >= 1e3 ? `${(h.amount / 1e3).toFixed(1)}K`
                      : h.amount.toFixed(h.decimals > 4 ? 4 : 2)}
                  </span>
                </div>
                <div style={{ fontSize: 10, color: 'var(--outline)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                  solana · {h.decimals} decimals
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {positions.length === 0 && holdings.length === 0 && (
        <div style={{ textAlign: 'center', padding: 'var(--sp-4)', color: 'var(--outline)', fontSize: 11 }}>
          No positions or holdings yet.
        </div>
      )}

      {/* ── Intelligence Feed ───────────────────────────────────── */}
      <div>
        <div className="section-header">
          <span className="section-title">Intelligence Feed</span>
          <span className="chip chip-purple">Live</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
          {decisions.length === 0 && (
            <div style={{ fontSize: 11, color: 'var(--outline)', padding: 'var(--sp-3) 0' }}>
              SAGE is scanning chains…
            </div>
          )}
          {decisions.map((d, i) => (
            <div key={i} className={`feed-item animate-in feed-item--${d.action === 'buy' ? 'green' : d.action === 'sell' ? 'red' : 'purple'}`}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-display)' }}>{d.token}</span>
                  <span className={`chip ${d.action === 'buy' ? 'chip-green' : d.action === 'sell' ? 'chip-red' : 'chip-purple'}`}>{d.action}</span>
                </div>
                {d.confidence != null && (
                  <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--on-surface-variant)' }}>
                    {(d.confidence * 100).toFixed(0)}%
                  </span>
                )}
              </div>
              <div style={{ fontSize: 10.5, color: 'var(--on-surface-variant)', lineHeight: 1.4 }}>
                {d.signal_type?.replace(/_/g, ' ') || 'Signal'} · {d.chain}
                {d.reasoning ? ` — ${d.reasoning.slice(0, 80)}` : ''}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

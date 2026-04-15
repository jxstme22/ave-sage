import { useEffect, useState } from 'react'
import { Briefcase, TrendingUp, TrendingDown, Wallet, Copy, Check } from 'lucide-react'
import * as api from '../api'

export default function Portfolio() {
  const [open, setOpen] = useState<any[]>([])
  const [closed, setClosed] = useState<any[]>([])
  const [holdings, setHoldings] = useState<any[]>([])
  const [feedback, setFeedback] = useState<any>(null)
  const [wallet, setWallet] = useState<any>(null)
  const [tab, setTab] = useState<'open' | 'closed' | 'holdings'>('open')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const load = () => {
      api.getOpenPositions().then(setOpen).catch(() => {})
      api.getClosedPositions().then(setClosed).catch(() => {})
      api.getWalletHoldings().then((h: any) => setHoldings(h?.holdings || [])).catch(() => {})
      api.getFeedbackStats().then(setFeedback).catch(() => {})
      api.getWalletBalance().then(setWallet).catch(() => {})
    }
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [])

  const totalPnl = closed.reduce((sum, p) => sum + (p.pnl_pct || 0), 0)
  const winCount = closed.filter(p => p.pnl_pct > 0).length
  const winRate = closed.length > 0 ? (winCount / closed.length) * 100 : 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-5)' }}>
      {/* ── Stats ────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 'var(--sp-4)' }}>
        <div className="stat-card">
          <span className="stat-label"><Wallet size={12} style={{ marginRight: 4 }} />Wallet Balance</span>
          <span className="stat-value" style={{ color: 'var(--primary)' }}>
            {wallet?.sol_balance != null ? `${wallet.sol_balance} SOL` : '—'}
          </span>
          <span className="stat-sub" style={{ fontSize: '0.6rem', display: 'flex', alignItems: 'center', gap: 4, cursor: wallet?.address ? 'pointer' : 'default' }}
            onClick={() => { if (wallet?.address) { navigator.clipboard.writeText(wallet.address); setCopied(true); setTimeout(() => setCopied(false), 1500) } }}
            title={wallet?.address || ''}>
            {wallet?.address ? `${wallet.address.slice(0, 6)}...${wallet.address.slice(-4)}` : 'Not connected'}
            {wallet?.address && (copied ? <Check size={10} color="var(--primary)" /> : <Copy size={10} />)}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Open Positions</span>
          <span className="stat-value">{open.length}</span>
          <span className="stat-sub">Active trades</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Closed Trades</span>
          <span className="stat-value">{closed.length}</span>
          <span className="stat-sub">{winCount} wins</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Win Rate</span>
          <span className="stat-value" style={{ color: winRate >= 50 ? 'var(--primary)' : 'var(--tertiary)' }}>
            {winRate.toFixed(0)}%
          </span>
          <span className="stat-sub">{closed.length} total trades</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Total P&L</span>
          <span className="stat-value" style={{ color: totalPnl >= 0 ? 'var(--primary)' : 'var(--tertiary)' }}>
            {totalPnl > 0 ? '+' : ''}{totalPnl.toFixed(1)}%
          </span>
          <span className="stat-sub">Cumulative</span>
        </div>
      </div>

      {/* ── Tab switcher ────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
        <button onClick={() => setTab('open')}
          className={tab === 'open' ? 'btn-primary' : 'btn-ghost'}
          style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 6 }}>
          <TrendingUp size={14} /> Open ({open.length})
        </button>
        <button onClick={() => setTab('closed')}
          className={tab === 'closed' ? 'btn-primary' : 'btn-ghost'}
          style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 6 }}>
          <TrendingDown size={14} /> Closed ({closed.length})
        </button>
        <button onClick={() => setTab('holdings')}
          className={tab === 'holdings' ? 'btn-primary' : 'btn-ghost'}
          style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 6 }}>
          <Briefcase size={14} /> Holdings ({holdings.length})
        </button>
      </div>

      {/* ── Position list ───────────────────────────────────── */}
      <div className="card" style={{ overflow: 'auto' }}>
        {tab !== 'holdings' ? (<>
        {/* Header */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: tab === 'open'
            ? '1fr 80px 80px 100px 100px 100px 80px'
            : '1fr 80px 80px 100px 100px 100px',
          gap: 'var(--sp-2)', padding: 'var(--sp-2) var(--sp-3)',
          background: 'var(--surface-container)', borderRadius: 'var(--radius-sm)', marginBottom: 'var(--sp-2)',
        }}>
          <span className="stat-label" style={{ fontSize: '0.6rem' }}>Token</span>
          <span className="stat-label" style={{ fontSize: '0.6rem' }}>Chain</span>
          <span className="stat-label" style={{ fontSize: '0.6rem' }}>Action</span>
          <span className="stat-label" style={{ fontSize: '0.6rem' }}>Entry</span>
          <span className="stat-label" style={{ fontSize: '0.6rem' }}>{tab === 'open' ? 'Current' : 'Exit'}</span>
          <span className="stat-label" style={{ fontSize: '0.6rem' }}>P&L</span>
          {tab === 'open' && <span className="stat-label" style={{ fontSize: '0.6rem' }}>Amount</span>}
        </div>

        {/* Rows */}
        {(tab === 'open' ? open : closed).length === 0 && (
          <div style={{ padding: 'var(--sp-5)', color: 'var(--outline)', fontSize: '0.8rem', textAlign: 'center' }}>
            No {tab} positions.
          </div>
        )}
        {(tab === 'open' ? open : closed).map((p: any, i: number) => (
          <div key={i} style={{
            display: 'grid',
            gridTemplateColumns: tab === 'open'
              ? '1fr 80px 80px 100px 100px 100px 80px'
              : '1fr 80px 80px 100px 100px 100px',
            gap: 'var(--sp-2)', padding: 'var(--sp-3)',
            background: i % 2 === 0 ? 'transparent' : 'var(--surface-lowest)',
            borderRadius: 'var(--radius-sm)',
            alignItems: 'center',
          }}>
            <span style={{ fontWeight: 600, fontSize: '0.8rem' }}>{p.token}</span>
            <span className="chip chip-neutral" style={{ fontSize: '0.55rem', justifySelf: 'start' }}>
              {(p.chain || '').toUpperCase()}
            </span>
            <span className={`chip ${p.action === 'buy' ? 'chip-green' : 'chip-red'}`} style={{ fontSize: '0.55rem', justifySelf: 'start' }}>
              {p.action}
            </span>
            <span className="text-mono" style={{ fontSize: '0.7rem' }}>
              ${p.entry?.toFixed(6)}
            </span>
            <span className="text-mono" style={{ fontSize: '0.7rem' }}>
              ${(tab === 'open' ? p.current : p.exit)?.toFixed(6)}
            </span>
            <span className="text-mono" style={{
              fontSize: '0.8rem', fontWeight: 600,
              color: p.pnl_pct >= 0 ? 'var(--primary)' : 'var(--tertiary)',
            }}>
              {p.pnl_pct > 0 ? '+' : ''}{p.pnl_pct}%
            </span>
            {tab === 'open' && (
              <span className="text-mono" style={{ fontSize: '0.7rem', color: 'var(--outline)' }}>
                ${p.amount_usd?.toFixed(0)}
              </span>
            )}
          </div>
        ))}
        </>) : (<>
        {/* Holdings header */}
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 120px 80px',
          gap: 'var(--sp-2)', padding: 'var(--sp-2) var(--sp-3)',
          background: 'var(--surface-container)', borderRadius: 'var(--radius-sm)', marginBottom: 'var(--sp-2)',
        }}>
          <span className="stat-label" style={{ fontSize: '0.6rem' }}>Token Mint</span>
          <span className="stat-label" style={{ fontSize: '0.6rem' }}>Amount</span>
          <span className="stat-label" style={{ fontSize: '0.6rem' }}>Chain</span>
        </div>
        {holdings.length === 0 && (
          <div style={{ padding: 'var(--sp-5)', color: 'var(--outline)', fontSize: '0.8rem', textAlign: 'center' }}>
            No token holdings.
          </div>
        )}
        {holdings.map((h: any, i: number) => (
          <div key={i} style={{
            display: 'grid', gridTemplateColumns: '1fr 120px 80px',
            gap: 'var(--sp-2)', padding: 'var(--sp-3)',
            background: i % 2 === 0 ? 'transparent' : 'var(--surface-lowest)',
            borderRadius: 'var(--radius-sm)', alignItems: 'center',
          }}>
            <span className="text-mono" style={{ fontSize: '0.7rem' }}>
              {h.mint?.slice(0, 8)}…{h.mint?.slice(-6)}
            </span>
            <span className="text-mono" style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--primary)' }}>
              {h.amount >= 1e9 ? `${(h.amount / 1e9).toFixed(2)}B`
                : h.amount >= 1e6 ? `${(h.amount / 1e6).toFixed(2)}M`
                : h.amount >= 1e3 ? `${(h.amount / 1e3).toFixed(1)}K`
                : h.amount.toFixed(2)}
            </span>
            <span className="chip chip-neutral" style={{ fontSize: '0.55rem', justifySelf: 'start' }}>SOLANA</span>
          </div>
        ))}
        </>)}
      </div>

      {/* ── Feedback ────────────────────────────────────────── */}
      {feedback && (
        <div className="glass" style={{ borderRadius: 'var(--radius-lg)', padding: 'var(--sp-5)' }}>
          <div className="text-display" style={{ fontSize: '0.8rem', color: 'var(--secondary)', marginBottom: 'var(--sp-3)' }}>
            Learning Feedback Loop
          </div>
          <pre style={{ fontSize: '0.7rem', fontFamily: 'var(--font-mono)', color: 'var(--on-surface-variant)', overflow: 'auto' }}>
            {JSON.stringify(feedback, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

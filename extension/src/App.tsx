import { useState } from 'react'
import { Wallet, ArrowLeftRight, Radio, MessageCircle } from 'lucide-react'
import WalletPage from './pages/WalletPage'
import SwapPage from './pages/SwapPage'
import SignalsPage from './pages/SignalsPage'
import SageSaysPage from './pages/SageSaysPage'

type Tab = 'wallet' | 'swap' | 'signals' | 'sage'

const TABS: { id: Tab; icon: typeof Wallet; label: string }[] = [
  { id: 'wallet',  icon: Wallet,         label: 'Wallet'  },
  { id: 'swap',    icon: ArrowLeftRight,  label: 'Swap'    },
  { id: 'signals', icon: Radio,           label: 'Signals' },
  { id: 'sage',    icon: MessageCircle,   label: 'SAGE'    },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('wallet')

  return (
    <>
      {/* Accent line */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 1, zIndex: 100,
        background: 'linear-gradient(90deg, transparent, var(--primary) 40%, var(--secondary) 70%, transparent)',
        opacity: 0.45,
      }} />

      {/* Top bar */}
      <nav className="top-nav">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="text-display" style={{
            fontSize: '0.92rem', color: 'var(--primary)', letterSpacing: '0.16em', textTransform: 'uppercase',
          }}>
            AVE
          </span>
          <span className="text-display" style={{
            fontSize: '0.92rem', color: 'var(--on-surface-variant)', letterSpacing: '0.16em', textTransform: 'uppercase',
          }}>
            SAGE
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 5,
            background: 'var(--surface-low)', padding: '3px 9px', borderRadius: 'var(--radius-full)',
            border: '1px solid rgba(255,255,255,0.05)',
          }}>
            <div className="pulse-dot" />
            <span style={{ fontSize: 9, fontWeight: 700, color: 'var(--primary)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
              Solana
            </span>
          </div>
        </div>
      </nav>

      {/* Content */}
      <main style={{ flex: 1, overflow: 'auto', padding: '0 var(--sp-4)', paddingBottom: 72 }}>
        {tab === 'wallet'  && <WalletPage />}
        {tab === 'swap'    && <SwapPage />}
        {tab === 'signals' && <SignalsPage />}
        {tab === 'sage'    && <SageSaysPage />}
      </main>

      {/* Bottom nav */}
      <footer className="tab-nav" style={{ position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 50 }}>
        {TABS.map(({ id, icon: Icon, label }) => (
          <button key={id} className={`tab-item ${tab === id ? 'active' : ''}`} onClick={() => setTab(id)}>
            <Icon size={18} strokeWidth={tab === id ? 2.2 : 1.8} />
            <span className="label">{label}</span>
          </button>
        ))}
      </footer>
    </>
  )
}

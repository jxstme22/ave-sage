import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Activity, Brain, Briefcase, ShieldCheck, MessageCircle, Settings,
} from 'lucide-react'
import { useWebSocket } from './useWebSocket'
import CommandCenter from './pages/CommandCenter'
import MarketPulse from './pages/MarketPulse'
import ReasoningEngine from './pages/ReasoningEngine'
import Portfolio from './pages/Portfolio'
import RiskAssessment from './pages/RiskAssessment'
import SageChat from './pages/SageChat'

const NAV = [
  { to: '/', icon: LayoutDashboard, label: 'Command Center' },
  { to: '/pulse', icon: Activity, label: 'Market Pulse' },
  { to: '/reasoning', icon: Brain, label: 'Reasoning Engine' },
  { to: '/portfolio', icon: Briefcase, label: 'Portfolio' },
  { to: '/risk', icon: ShieldCheck, label: 'Risk Assessment' },
  { to: '/chat', icon: MessageCircle, label: 'SAGE Chat' },
]

export default function App() {
  const ws = useWebSocket()
  const location = useLocation()

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw' }}>
      {/* ── Sidebar ─────────────────────────────────────────────── */}
      <nav style={{
        width: 220,
        minWidth: 220,
        background: 'var(--surface)',
        display: 'flex',
        flexDirection: 'column',
        padding: 'var(--sp-5) 0',
        overflow: 'hidden',
      }}>
        {/* Brand */}
        <div style={{
          padding: '0 var(--sp-5)',
          marginBottom: 'var(--sp-8)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--sp-3)',
        }}>
          <div style={{
            width: 36, height: 36,
            borderRadius: 'var(--radius-md)',
            background: 'linear-gradient(135deg, var(--primary), var(--primary-container))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Brain size={20} color="var(--on-primary)" />
          </div>
          <div>
            <div className="text-display" style={{ fontSize: '0.85rem', color: 'var(--primary)' }}>
              SAGE AI
            </div>
            <div style={{ fontSize: '0.65rem', color: 'var(--outline)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              {ws.connected ? 'Terminal Active' : 'Disconnected'}
            </div>
          </div>
        </div>

        {/* Nav links */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, flex: 1 }}>
          {NAV.map(({ to, icon: Icon, label }) => {
            const active = location.pathname === to
            return (
              <NavLink key={to} to={to} style={{
                display: 'flex', alignItems: 'center', gap: 'var(--sp-3)',
                padding: 'var(--sp-3) var(--sp-5)',
                color: active ? 'var(--primary)' : 'var(--on-surface-variant)',
                textDecoration: 'none',
                fontSize: '0.85rem',
                fontWeight: active ? 600 : 400,
                borderLeft: active ? '3px solid var(--primary)' : '3px solid transparent',
                background: active ? 'rgba(68, 224, 146, 0.05)' : 'transparent',
                transition: 'all 0.15s',
              }}>
                <Icon size={18} />
                {label}
              </NavLink>
            )
          })}
        </div>

        {/* Status footer */}
        <div style={{ padding: 'var(--sp-4) var(--sp-5)', display: 'flex', flexDirection: 'column', gap: 'var(--sp-3)' }}>
          <NavLink to="/settings" style={{
            display: 'flex', alignItems: 'center', gap: 'var(--sp-3)',
            color: 'var(--on-surface-variant)', textDecoration: 'none', fontSize: '0.8rem',
          }}>
            <Settings size={16} /> System Status
          </NavLink>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
            <div className="pulse-dot" style={{ background: ws.connected ? 'var(--primary)' : 'var(--tertiary)' }} />
            <span style={{ fontSize: '0.7rem', color: 'var(--outline)' }}>
              {ws.connected ? 'WebSocket Connected' : 'Reconnecting...'}
            </span>
          </div>
        </div>
      </nav>

      {/* ── Main content ────────────────────────────────────────── */}
      <main style={{
        flex: 1,
        overflow: 'auto',
        background: 'var(--surface-lowest)',
      }}>
        {/* Top bar */}
        <header style={{
          position: 'sticky',
          top: 0,
          zIndex: 10,
          background: 'var(--surface-lowest)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: 'var(--sp-3) var(--sp-6)',
          borderBottom: '1px solid var(--outline-variant)',
        }}>
          <div className="text-display" style={{ fontSize: '1.1rem', color: 'var(--primary)' }}>
            AVE SAGE
          </div>
          <div style={{ display: 'flex', gap: 'var(--sp-6)', alignItems: 'center' }}>
            {([
              { label: 'Terminal', to: '/' },
              { label: 'Intelligence', to: '/reasoning' },
              { label: 'Signals', to: '/pulse' },
            ] as const).map(({ label, to }) => {
              const active = to === '/'
                ? location.pathname === '/'
                : location.pathname.startsWith(to)
              return (
                <NavLink key={to} to={to} style={{
                  fontSize: '0.8rem',
                  color: active ? 'var(--on-surface)' : 'var(--outline)',
                  textDecoration: active ? 'underline' : 'none',
                  textUnderlineOffset: 6,
                  textDecorationColor: 'var(--primary)',
                  cursor: 'pointer',
                  textDecorationThickness: 2,
                }}>
                  {label}
                </NavLink>
              )
            })}
          </div>
        </header>

        {/* Page */}
        <div style={{ padding: 'var(--sp-6)' }}>
          <Routes>
            <Route path="/" element={<CommandCenter ws={ws} />} />
            <Route path="/pulse" element={<MarketPulse ws={ws} />} />
            <Route path="/reasoning" element={<ReasoningEngine />} />
            <Route path="/portfolio" element={<Portfolio />} />
            <Route path="/risk" element={<RiskAssessment />} />
            <Route path="/chat" element={<SageChat />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}

import { useState, useRef, useEffect, useCallback } from 'react'
import { Bot, User, Send, Trash2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import * as api from '../api'

interface Msg { role: 'user' | 'sage'; text: string; ts: number }

const STORAGE_KEY = 'sage_ext_chat_v1'
const WELCOME: Msg = {
  role: 'sage',
  text: "I'm **SAGE** — your on-chain trading intelligence. Ask me about signals, positions, tokens, or market conditions.",
  ts: Date.now(),
}

function loadHistory(): Msg[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const p = JSON.parse(raw) as Msg[]
      if (Array.isArray(p) && p.length) return p
    }
  } catch { /* ignore */ }
  return [WELCOME]
}

export default function SageSaysPage() {
  const [msgs, setMsgs] = useState<Msg[]>(loadHistory)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, loading])

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(msgs.slice(-80))) } catch { /* ignore */ }
  }, [msgs])

  const send = useCallback(async () => {
    const q = input.trim()
    if (!q || loading) return
    setInput('')
    setMsgs(p => [...p, { role: 'user', text: q, ts: Date.now() }])
    setLoading(true)
    try {
      const res = await api.askSage(q)
      setMsgs(p => [...p, { role: 'sage', text: res.answer || res.response || JSON.stringify(res), ts: Date.now() }])
    } catch (e: any) {
      setMsgs(p => [...p, { role: 'sage', text: `**Error:** ${e.message}`, ts: Date.now() }])
    }
    setLoading(false)
  }, [input, loading])

  const clearHistory = () => {
    const fresh = [{ ...WELCOME, ts: Date.now() }]
    setMsgs(fresh)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(fresh))
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(600px - 44px - 64px)', paddingTop: 'var(--sp-2)' }}>

      {/* ── Clear button ────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', paddingBottom: 4 }}>
        <button
          onClick={clearHistory}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--outline)', fontSize: 10, display: 'flex', alignItems: 'center', gap: 3,
            padding: '2px 6px', borderRadius: 'var(--radius-sm)',
          }}
        >
          <Trash2 size={10} /> Clear
        </button>
      </div>

      {/* ── Messages ────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 'var(--sp-3)', paddingBottom: 'var(--sp-2)' }}>
        {msgs.map((m, i) => (
          <div key={i} className="animate-in" style={{
            display: 'flex', gap: 'var(--sp-2)',
            flexDirection: m.role === 'user' ? 'row-reverse' : 'row',
            alignItems: 'flex-start',
          }}>
            {/* Avatar */}
            <div style={{
              width: 24, height: 24, borderRadius: 'var(--radius-md)', flexShrink: 0,
              background: m.role === 'sage' ? 'var(--surface-container)' : 'var(--surface-high)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              border: '1px solid rgba(255,255,255,0.05)',
            }}>
              {m.role === 'sage' ? <Bot size={12} color="var(--secondary)" /> : <User size={12} color="var(--on-surface-variant)" />}
            </div>

            {/* Bubble */}
            <div style={{
              maxWidth: '78%',
              padding: '8px 10px',
              borderRadius: m.role === 'sage'
                ? '3px var(--radius-md) var(--radius-md) var(--radius-md)'
                : 'var(--radius-md) 3px var(--radius-md) var(--radius-md)',
              background: m.role === 'sage'
                ? 'var(--surface-container)'
                : 'linear-gradient(135deg, rgba(68,224,146,0.08), rgba(201,191,255,0.06))',
              border: m.role === 'sage'
                ? '1px solid rgba(255,255,255,0.04)'
                : '1px solid rgba(68,224,146,0.12)',
              lineHeight: 1.55, wordBreak: 'break-word', minWidth: 0,
            }}>
              {m.role === 'user' ? (
                <span style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>{m.text}</span>
              ) : (
                <div className="sage-md">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
                </div>
              )}
              <div style={{ fontSize: 8.5, color: 'var(--outline)', marginTop: 4, textAlign: m.role === 'user' ? 'right' : 'left', userSelect: 'none' }}>
                {new Date(m.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display: 'flex', gap: 'var(--sp-2)', alignItems: 'flex-start' }}>
            <div style={{ width: 24, height: 24, borderRadius: 'var(--radius-md)', flexShrink: 0, background: 'var(--surface-container)', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid rgba(255,255,255,0.05)' }}>
              <Bot size={12} color="var(--secondary)" />
            </div>
            <div style={{ padding: '8px 10px', borderRadius: 'var(--radius-md)', background: 'var(--surface-container)', border: '1px solid rgba(255,255,255,0.04)' }}>
              <Dots />
            </div>
          </div>
        )}
        <div ref={bottom} />
      </div>

      {/* ── Input ───────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', gap: 'var(--sp-2)', alignItems: 'center',
        background: 'var(--surface-low)', borderRadius: 'var(--radius-lg)',
        padding: '6px 10px', marginTop: 'var(--sp-2)',
        border: '1px solid rgba(255,255,255,0.05)',
      }}>
        <input
          className="input"
          style={{ border: 'none', background: 'transparent', flex: 1, fontSize: 12, padding: 0 }}
          placeholder="Ask SAGE…"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          disabled={loading}
        />
        <button
          onClick={send}
          disabled={loading || !input.trim()}
          className="btn-primary"
          style={{ padding: '5px 10px', opacity: (loading || !input.trim()) ? 0.35 : 1, display: 'flex', alignItems: 'center' }}
        >
          <Send size={12} />
        </button>
      </div>
    </div>
  )
}

function Dots() {
  return (
    <span style={{ display: 'inline-flex', gap: 3, alignItems: 'center' }}>
      {[0, 1, 2].map(i => (
        <span key={i} style={{
          width: 5, height: 5, borderRadius: '50%', background: 'var(--secondary)',
          animation: `dotPulse 1.2s ease-in-out ${i * 0.15}s infinite`,
        }} />
      ))}
      <style>{`@keyframes dotPulse { 0%,80%,100% { opacity:0.3; transform:scale(0.8); } 40% { opacity:1; transform:scale(1.2); } }`}</style>
    </span>
  )
}

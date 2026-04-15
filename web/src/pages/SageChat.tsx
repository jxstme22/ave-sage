import { useState, useRef, useEffect, useCallback } from 'react'
import { Bot, User, Send, Trash2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import * as api from '../api'

interface ChatMsg {
  role: 'user' | 'sage'
  text: string
  ts: number
}

const STORAGE_KEY = 'sage_chat_history_v1'
const WELCOME: ChatMsg = {
  role: 'sage',
  text: "Hey — I'm **SAGE**, your on-chain trading intelligence. Ask me about tokens, market conditions, open positions, recent trades, or anything in my memory. 🟢",
  ts: Date.now(),
}

function loadHistory(): ChatMsg[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as ChatMsg[]
      if (Array.isArray(parsed) && parsed.length > 0) return parsed
    }
  } catch { /* ignore */ }
  return [WELCOME]
}

export default function SageChat() {
  const [msgs, setMsgs] = useState<ChatMsg[]>(loadHistory)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Persist to localStorage whenever msgs changes
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(msgs.slice(-120)))
    } catch { /* storage full, ignore */ }
  }, [msgs])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [msgs, loading])

  const send = useCallback(async () => {
    const q = input.trim()
    if (!q || loading) return
    setInput('')
    const userMsg: ChatMsg = { role: 'user', text: q, ts: Date.now() }
    setMsgs(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const res = await api.askSage(q)
      const answer = res.answer || 'No response received.'
      setMsgs(prev => [...prev, { role: 'sage', text: answer, ts: Date.now() }])
    } catch (e: any) {
      setMsgs(prev => [...prev, { role: 'sage', text: `⚠ **Error**: ${e.message}`, ts: Date.now() }])
    }
    setLoading(false)
  }, [input, loading])

  const clearHistory = () => {
    const fresh = [{ ...WELCOME, ts: Date.now() }]
    setMsgs(fresh)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(fresh))
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 100px)' }}>
      <style>{MARKDOWN_STYLES}</style>

      {/* ── Header ─────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: 'var(--sp-2) var(--sp-4) 0',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Bot size={16} color="var(--secondary)" />
          <span style={{ fontSize: '0.78rem', color: 'var(--on-surface-variant)', fontWeight: 500, letterSpacing: '0.04em' }}>
            SAGE INTELLIGENCE CHAT
          </span>
        </div>
        <button
          onClick={clearHistory}
          title="Clear chat history"
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 4,
            color: 'var(--outline)', fontSize: '0.72rem', padding: '4px 8px',
            borderRadius: 'var(--radius-sm)',
            transition: 'color 0.15s',
          }}
          onMouseOver={e => (e.currentTarget.style.color = 'var(--error, #ff6b6b)')}
          onMouseOut={e => (e.currentTarget.style.color = 'var(--outline)')}
        >
          <Trash2 size={12} /> Clear
        </button>
      </div>

      {/* ── Message area ───────────────────────────────────────── */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: 'var(--sp-3) var(--sp-4)',
        display: 'flex', flexDirection: 'column', gap: 'var(--sp-3)',
      }}>
        {msgs.map((m, i) => (
          <div key={i} className="animate-in" style={{
            display: 'flex', gap: 'var(--sp-3)',
            flexDirection: m.role === 'user' ? 'row-reverse' : 'row',
            alignItems: 'flex-start',
          }}>
            {/* Avatar */}
            <div style={{
              width: 32, height: 32, borderRadius: 'var(--radius-md)', flexShrink: 0,
              background: m.role === 'sage' ? 'var(--surface-container)' : 'var(--surface-high)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {m.role === 'sage'
                ? <Bot size={16} color="var(--secondary)" />
                : <User size={16} color="var(--on-surface-variant)" />}
            </div>

            {/* Bubble */}
            <div style={{
              maxWidth: '76%',
              padding: 'var(--sp-3) var(--sp-4)',
              borderRadius: m.role === 'sage'
                ? '4px var(--radius-lg) var(--radius-lg) var(--radius-lg)'
                : 'var(--radius-lg) 4px var(--radius-lg) var(--radius-lg)',
              background: m.role === 'sage'
                ? 'var(--surface-container)'
                : 'linear-gradient(135deg, rgba(68,224,146,0.10), rgba(201,191,255,0.07))',
              border: m.role === 'sage'
                ? '1px solid rgba(255,255,255,0.04)'
                : '1px solid rgba(68,224,146,0.15)',
              fontSize: '0.85rem', lineHeight: 1.6,
              color: 'var(--on-surface)',
              wordBreak: 'break-word',
              minWidth: 0,
            }}>
              {m.role === 'user' ? (
                <span style={{ whiteSpace: 'pre-wrap' }}>{m.text}</span>
              ) : (
                <div className="sage-md">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
                </div>
              )}
              <div style={{
                fontSize: '0.6rem', color: 'var(--outline)', marginTop: 'var(--sp-2)',
                textAlign: m.role === 'user' ? 'right' : 'left',
                userSelect: 'none',
              }}>
                {new Date(m.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display: 'flex', gap: 'var(--sp-3)', alignItems: 'flex-start' }}>
            <div style={{
              width: 32, height: 32, borderRadius: 'var(--radius-md)', flexShrink: 0,
              background: 'var(--surface-container)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Bot size={16} color="var(--secondary)" />
            </div>
            <div style={{
              padding: 'var(--sp-3) var(--sp-4)', borderRadius: 'var(--radius-lg)',
              background: 'var(--surface-container)', border: '1px solid rgba(255,255,255,0.04)',
              fontSize: '0.8rem', color: 'var(--on-surface-variant)',
            }}>
              <TypingDots />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Input bar ──────────────────────────────────────────── */}
      <div style={{
        display: 'flex', gap: 'var(--sp-2)', alignItems: 'flex-end',
        background: 'var(--surface-low)', borderRadius: 'var(--radius-lg)',
        padding: 'var(--sp-3) var(--sp-4)', margin: '0 var(--sp-3) var(--sp-3)',
        border: '1px solid rgba(255,255,255,0.05)',
      }}>
        <textarea
          className="input"
          rows={1}
          style={{
            border: 'none', background: 'transparent', flex: 1, fontSize: '0.85rem',
            resize: 'none', maxHeight: 120, overflowY: 'auto', lineHeight: 1.5,
            padding: '2px 0',
          }}
          placeholder="Ask SAGE anything — trades, signals, tokens, portfolio..."
          value={input}
          onChange={e => {
            setInput(e.target.value)
            // Auto-grow
            e.target.style.height = 'auto'
            e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
          }}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
          }}
          disabled={loading}
        />
        <button
          className="btn-primary"
          onClick={send}
          disabled={loading || !input.trim()}
          style={{
            padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 6,
            opacity: (loading || !input.trim()) ? 0.4 : 1, flexShrink: 0,
          }}
        >
          <Send size={14} /> Send
        </button>
      </div>
    </div>
  )
}

function TypingDots() {
  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
      {[0, 1, 2].map(i => (
        <span key={i} style={{
          width: 6, height: 6, borderRadius: '50%',
          background: 'var(--secondary)',
          animation: `pulse-dot-anim 1.2s ease-in-out ${i * 0.15}s infinite`,
        }} />
      ))}
      <style>{`
        @keyframes pulse-dot-anim {
          0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
          40%             { opacity: 1;   transform: scale(1.2); }
        }
      `}</style>
    </span>
  )
}

const MARKDOWN_STYLES = `
  .sage-md { min-width: 0; }
  .sage-md > *:first-child { margin-top: 0 !important; }
  .sage-md > *:last-child  { margin-bottom: 0 !important; }

  /* Paragraphs */
  .sage-md p { margin: 0 0 0.65em; }
  .sage-md p:last-child { margin-bottom: 0; }

  /* Headings */
  .sage-md h1,.sage-md h2,.sage-md h3,.sage-md h4 {
    color: var(--on-surface);
    font-weight: 600;
    margin: 0.9em 0 0.35em;
    line-height: 1.3;
  }
  .sage-md h1 { font-size: 1.05em; }
  .sage-md h2 { font-size: 0.98em; border-bottom: 1px solid rgba(255,255,255,0.07); padding-bottom: 3px; }
  .sage-md h3 { font-size: 0.92em; }
  .sage-md h4 { font-size: 0.88em; color: var(--on-surface-variant); }

  /* Lists */
  .sage-md ul,.sage-md ol { padding-left: 1.4em; margin: 0.3em 0 0.6em; }
  .sage-md li { margin: 0.2em 0; }
  .sage-md li > p { margin: 0; }

  /* Bold / Italic */
  .sage-md strong { color: var(--on-surface); font-weight: 600; }
  .sage-md em { color: var(--on-surface-variant); font-style: italic; }

  /* Inline code */
  .sage-md code {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 0.82em;
    background: rgba(255,255,255,0.08);
    color: var(--secondary, #44e092);
    padding: 1px 5px;
    border-radius: 4px;
  }

  /* Code blocks */
  .sage-md pre {
    background: rgba(0,0,0,0.35);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px;
    padding: 10px 14px;
    overflow-x: auto;
    margin: 0.5em 0;
  }
  .sage-md pre code {
    background: none;
    padding: 0;
    color: #e2e8f0;
    font-size: 0.8em;
  }

  /* Blockquote */
  .sage-md blockquote {
    border-left: 3px solid var(--secondary, #44e092);
    margin: 0.5em 0;
    padding: 2px 0 2px 12px;
    color: var(--on-surface-variant);
    font-style: italic;
  }

  /* Horizontal rule */
  .sage-md hr {
    border: none;
    border-top: 1px solid rgba(255,255,255,0.08);
    margin: 0.75em 0;
  }

  /* Links */
  .sage-md a {
    color: var(--secondary, #44e092);
    text-decoration: underline;
    text-underline-offset: 2px;
    text-decoration-color: rgba(68,224,146,0.4);
  }
  .sage-md a:hover { text-decoration-color: var(--secondary, #44e092); }

  /* Tables */
  .sage-md table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82em;
    margin: 0.6em 0;
    border-radius: 6px;
    overflow: hidden;
  }
  .sage-md thead tr {
    background: rgba(68,224,146,0.09);
  }
  .sage-md th {
    padding: 6px 12px;
    text-align: left;
    font-weight: 600;
    color: var(--secondary, #44e092);
    border-bottom: 1px solid rgba(68,224,146,0.2);
    white-space: nowrap;
  }
  .sage-md td {
    padding: 5px 12px;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    color: var(--on-surface);
  }
  .sage-md tbody tr:last-child td { border-bottom: none; }
  .sage-md tbody tr:hover td { background: rgba(255,255,255,0.03); }

  /* Number / $ alignment in tables */
  .sage-md td:not(:first-child) { text-align: right; }
  .sage-md th:not(:first-child) { text-align: right; }
`

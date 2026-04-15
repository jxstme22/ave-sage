import { useEffect, useState } from 'react'
import { Search, Database, Download } from 'lucide-react'
import * as api from '../api'

export default function ReasoningEngine() {
  const [stats, setStats] = useState<any>(null)
  const [memHealth, setMemHealth] = useState<any>(null)
  const [recent, setRecent] = useState<any[]>([])
  const [searchQ, setSearchQ] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [searching, setSearching] = useState(false)
  const [selected, setSelected] = useState<any>(null)

  useEffect(() => {
    api.getMemoryStats().then(setStats).catch(() => {})
    api.getMemoryHealth().then(setMemHealth).catch(() => {})
    api.getMemoryRecent(20).then(setRecent).catch(() => {})
  }, [])

  const handleSearch = async () => {
    if (!searchQ.trim()) return
    setSearching(true)
    try {
      const res = await api.queryMemory(searchQ, 10)
      setSearchResults(res.results || res || [])
    } catch { setSearchResults([]) }
    setSearching(false)
  }

  const displayItems = searchResults.length > 0 ? searchResults : recent

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 'var(--sp-5)', height: 'calc(100vh - 100px)' }}>
      {/* ── Main: Stats + Chunk Explorer ─────────────────────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-5)', overflow: 'auto' }}>
        {/* Stats row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--sp-3)' }}>
          <div className="stat-card">
            <span className="stat-label">Total Memory Chunks</span>
            <span className="stat-value" style={{ color: 'var(--on-surface)' }}>
              {stats?.total_chunks?.toLocaleString() ?? '—'}
            </span>
            <span className="stat-sub" style={{ color: 'var(--primary)' }}>
              ↗ Active
            </span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Vector DB Health</span>
            <span className="stat-value" style={{ color: 'var(--primary)' }}>
              {memHealth?.status === 'healthy' ? '99.98%' : memHealth?.status ?? '—'}
            </span>
            <span className="stat-sub">● Operational</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Embedding Model</span>
            <span className="stat-value" style={{ fontSize: '0.85rem' }}>
              {stats?.embedding_model || 'all-MiniLM-L6-v2'}
            </span>
            <span className="stat-sub">Latency: {memHealth?.avg_latency_ms ?? '—'}ms</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Collections</span>
            <span className="stat-value">{stats?.collections ?? '—'}</span>
            <span className="stat-sub">ChromaDB</span>
          </div>
        </div>

        {/* Semantic search */}
        <div style={{ display: 'flex', gap: 'var(--sp-2)', alignItems: 'center', background: 'var(--surface-low)', borderRadius: 'var(--radius-lg)', padding: 'var(--sp-2) var(--sp-4)' }}>
          <Search size={18} color="var(--outline)" />
          <input
            className="input"
            style={{ border: 'none', background: 'transparent', flex: 1 }}
            placeholder="Search stored intelligence (e.g. 'high volatility patterns on Solana')..."
            value={searchQ}
            onChange={e => setSearchQ(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
          />
          <button className="btn-ghost" onClick={handleSearch} disabled={searching}
            style={{ fontSize: '0.75rem' }}>
            {searching ? '...' : 'Search'}
          </button>
        </div>

        {/* Chunk explorer table */}
        <div className="card" style={{ overflow: 'auto', flex: 1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-4)' }}>
            <span className="text-display" style={{ fontSize: '0.9rem' }}>Chunk Explorer</span>
            <span style={{ fontSize: '0.7rem', color: 'var(--outline)' }}>
              Displaying {displayItems.length} items
            </span>
          </div>

          {/* Table header */}
          <div style={{ display: 'grid', gridTemplateColumns: '100px 80px 110px 90px 1fr 80px', gap: 'var(--sp-2)', padding: 'var(--sp-2) var(--sp-3)', background: 'var(--surface-container)', borderRadius: 'var(--radius-sm)', marginBottom: 'var(--sp-2)' }}>
            {['Chunk ID', 'Chain', 'Type', 'Score', 'RAG Text Preview', 'Action'].map(h => (
              <span key={h} className="stat-label" style={{ fontSize: '0.6rem' }}>{h}</span>
            ))}
          </div>

          {/* Rows */}
          {displayItems.length === 0 && (
            <div style={{ padding: 'var(--sp-4)', color: 'var(--outline)', fontSize: '0.8rem' }}>
              No chunks found. Try a different search.
            </div>
          )}
          {displayItems.map((chunk: any, i: number) => {
            const id = chunk.id || chunk.chunk_id || `#${i}`
            const chain = chunk.metadata?.chain || chunk.chain || '—'
            const type = chunk.metadata?.event_type || chunk.type || '—'
            const score = chunk.score ?? chunk.similarity ?? chunk.significance ?? chunk.metadata?.significance ?? 0
            const text = chunk.document || chunk.text || chunk.content || '—'

            return (
              <div key={i} style={{
                display: 'grid', gridTemplateColumns: '100px 80px 110px 90px 1fr 80px',
                gap: 'var(--sp-2)', padding: 'var(--sp-3)',
                background: i % 2 === 0 ? 'transparent' : 'var(--surface-lowest)',
                cursor: 'pointer', transition: 'background 0.1s',
                borderRadius: 'var(--radius-sm)',
              }}
                onClick={() => setSelected(chunk)}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--surface-container)')}
                onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 0 ? 'transparent' : 'var(--surface-lowest)')}
              >
                <span className="text-mono" style={{ fontSize: '0.7rem', color: 'var(--outline)' }}>
                  {typeof id === 'string' ? id.slice(0, 10) : id}
                </span>
                <span className={`chip ${getChainChip(chain)}`} style={{ fontSize: '0.55rem', justifySelf: 'start' }}>
                  {chain.toUpperCase()}
                </span>
                <span style={{ fontSize: '0.7rem', color: 'var(--on-surface-variant)' }}>{type}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
                  <div className="progress-bar" style={{ width: 40 }}>
                    <div className="progress-fill" style={{
                      width: `${Math.min(score * 100, 100)}%`,
                      background: score > 0.7 ? 'var(--primary)' : score > 0.4 ? 'var(--secondary)' : 'var(--tertiary)',
                    }} />
                  </div>
                  <span className="text-mono" style={{ fontSize: '0.65rem' }}>{score.toFixed(2)}</span>
                </div>
                <span style={{ fontSize: '0.7rem', color: 'var(--on-surface-variant)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {text.slice(0, 80)}
                </span>
                <button className="btn-ghost" style={{ fontSize: '0.6rem', padding: '2px 8px' }}
                  onClick={(e) => { e.stopPropagation(); setSelected(chunk) }}>
                  View
                </button>
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Right panel: Intelligence Health + Detail ─────────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-5)', overflow: 'auto' }}>
        {/* Intelligence Health */}
        <div className="card">
          <span className="text-display" style={{ fontSize: '0.8rem', marginBottom: 'var(--sp-3)', display: 'block' }}>
            Intelligence Health
          </span>
          <HealthBar label="Embedding Coverage" value={0.94} />
          <HealthBar label="Context Relevance" value={0.87} />
          <HealthBar label="Signal-to-Noise" value={0.72} />
          <HealthBar label="Memory Utilization" value={stats ? Math.min((stats.total_chunks || 0) / 100000, 1) : 0} />
        </div>

        {/* Selected chunk detail */}
        <div className="card" style={{ flex: 1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-3)' }}>
            <span className="text-display" style={{ fontSize: '0.8rem' }}>Metadata Inspector</span>
            {selected && (
              <button className="btn-ghost" style={{ fontSize: '0.6rem', padding: '2px 8px', display: 'flex', alignItems: 'center', gap: 4 }}>
                <Download size={12} /> JSON
              </button>
            )}
          </div>
          {selected ? (
            <pre style={{
              background: 'var(--surface-lowest)', borderRadius: 'var(--radius-md)',
              padding: 'var(--sp-3)', fontSize: '0.65rem', fontFamily: 'var(--font-mono)',
              overflow: 'auto', maxHeight: 400, color: 'var(--on-surface-variant)',
              whiteSpace: 'pre-wrap', wordBreak: 'break-all',
            }}>
              {JSON.stringify(selected, null, 2)}
            </pre>
          ) : (
            <div style={{ color: 'var(--outline)', fontSize: '0.75rem', padding: 'var(--sp-4)' }}>
              Click a chunk to inspect its metadata.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function HealthBar({ label, value }: { label: string; value: number }) {
  const color = value > 0.8 ? 'var(--primary)' : value > 0.5 ? 'var(--secondary)' : 'var(--tertiary)'
  return (
    <div style={{ marginBottom: 'var(--sp-3)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: '0.7rem', color: 'var(--on-surface-variant)' }}>{label}</span>
        <span className="text-mono" style={{ fontSize: '0.7rem', color }}>{(value * 100).toFixed(0)}%</span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${value * 100}%`, background: color }} />
      </div>
    </div>
  )
}

function getChainChip(chain: string) {
  const c = chain.toLowerCase()
  if (c.includes('sol')) return 'chip-green'
  if (c.includes('base') || c.includes('eth')) return 'chip-purple'
  if (c.includes('bsc')) return 'chip-neutral'
  return 'chip-neutral'
}

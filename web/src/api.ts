const BASE = ''  // proxied via Vite in dev

export async function api<T = any>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(path, window.location.origin)
  if (params) {
    for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v)
  }
  const res = await fetch(url.toString())
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

// ─── Typed API helpers ──────────────────────────────────────────────────────

export const getHealth = () => api('/health')
export const getMemoryStats = () => api('/api/memory/stats')
export const getMemoryRecent = (n = 20) => api('/api/memory/recent', { n: String(n) })
export const queryMemory = (q: string, n = 5) => api('/api/memory/query', { q, n: String(n) })
export const getDecisions = (n = 20) => api('/api/decisions', { n: String(n) })
export const getOpenPositions = () => api('/api/positions/open')
export const getClosedPositions = () => api('/api/positions/closed')
export const askSage = (q: string) => api('/api/sage/ask', { q })
export const getFeedbackStats = () => api('/api/feedback/stats')
export const getMemoryHealth = () => api('/api/memory/health')
export const getSignalPerformance = (signal_type: string, chain?: string) =>
  api('/api/signals/performance', { signal_type, ...(chain ? { chain } : {}) })
export const getRulesStatus = () => api('/api/rules/status')
export const getStrategyLedger = () => api('/api/strategy/ledger')
export const getStrategyTune = () => api('/api/strategy/tune')
export const getWalletBalance = () => api('/api/wallet/balance')
export const getWalletHoldings = () => api('/api/wallet/holdings')
export const executeTrade = (token: string, chain: string, action: string, amount_usd: number, symbol: string) => {
  const url = new URL('/api/trade/execute', window.location.origin)
  url.searchParams.set('token', token)
  url.searchParams.set('chain', chain)
  url.searchParams.set('action', action)
  url.searchParams.set('amount_usd', String(amount_usd))
  url.searchParams.set('symbol', symbol)
  return fetch(url.toString(), { method: 'POST' }).then(r => r.json())
}

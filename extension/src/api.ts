const BASE = 'http://localhost:8000'

async function api<T = any>(path: string, params?: Record<string, any>): Promise<T> {
  const qs = params ? '?' + new URLSearchParams(params as any).toString() : ''
  const r = await fetch(`${BASE}${path}${qs}`)
  if (!r.ok) throw new Error(`API ${r.status}`)
  return r.json()
}

export const getHealth = () => api('/health')
export const getDecisions = (n = 10) => api('/api/decisions', { n: String(n) })
export const getOpenPositions = () => api('/api/positions/open')
export const getClosedPositions = () => api('/api/positions/closed')
export const askSage = (q: string) => api('/api/sage/ask', { q })
export const getSignalPerformance = () => api('/api/signals/performance')
export const getRulesStatus = () => api('/api/rules/status')
export const getFeedbackStats = () => api('/api/feedback/stats')
export const getMemoryStats = () => api('/api/memory/stats')
export const queryMemory = (q: string, k = 5) => api('/api/memory/query', { q, n: String(k) })
export const getWalletBalance = () => api('/api/wallet/balance')
export const getWalletHoldings = () => api('/api/wallet/holdings')

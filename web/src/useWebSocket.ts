import { useEffect, useRef, useState, useCallback } from 'react'

export interface WsMessage {
  type: string
  [key: string]: any
}

export function useWebSocket() {
  const [messages, setMessages] = useState<WsMessage[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null!)
  const reconnectTimer = useRef<number>(0)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`)

    ws.onopen = () => {
      setConnected(true)
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    }

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as WsMessage
        setMessages(prev => [msg, ...prev].slice(0, 200))
      } catch { /* ignore non-JSON */ }
    }

    ws.onclose = () => {
      setConnected(false)
      reconnectTimer.current = window.setTimeout(connect, 3000)
    }

    ws.onerror = () => ws.close()
    wsRef.current = ws
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  const clearMessages = useCallback(() => setMessages([]), [])

  return { messages, connected, clearMessages }
}

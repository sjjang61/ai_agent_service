import { useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '../store/authStore'

export function useWebSocket(
  conversationId: string | null,
  onMessage: (data: unknown) => void
) {
  const wsRef = useRef<WebSocket | null>(null)
  const { token } = useAuthStore()

  const connect = useCallback(() => {
    if (!conversationId || !token) return
    const ws = new WebSocket(
      `ws://localhost:8500/ws/chat/${conversationId}?token=${token}`
    )
    ws.onmessage = (e) => {
      try {
        onMessage(JSON.parse(e.data))
      } catch {}
    }
    ws.onclose = () => {
      wsRef.current = null
    }
    wsRef.current = ws
    return ws
  }, [conversationId, token, onMessage])

  useEffect(() => {
    const ws = connect()
    return () => {
      ws?.close()
    }
  }, [connect])

  const send = useCallback((data: unknown) => {
    wsRef.current?.send(JSON.stringify(data))
  }, [])

  return { send, connected: !!wsRef.current }
}

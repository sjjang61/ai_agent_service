import { useEffect } from 'react'
import { chatApi } from '../api/chat'
import { useAgentStore } from '../store/agentStore'
import { useChatStore } from '../store/chatStore'
import { isStreaming, releaseStream } from './useAgentStream'
import type { Message } from '../types/chat'

const INTERVAL_MS = 4000
const MISSES = 2 // 요청 직후의 짧은 어긋남을 넘기려고 연속으로 '실행 중 아님' 일 때만 정리한다

/**
 * 화면은 '실행 중'인데 서버에는 실행이 없으면(서버 재시작·연결 끊김 등) 실행 중 표시를 끄고 서버의 저장 내용으로 맞춘다.
 * 정상 스트리밍 중에는 서버도 실행 중이므로 아무 일도 하지 않는다.
 */
export function useRunWatchdog(conversationId: string | null, running: boolean) {
  useEffect(() => {
    if (!conversationId || !running) return
    let misses = 0
    let stopped = false
    const tick = async () => {
      try {
        const { data } = await chatApi.runStatus(conversationId)
        if (stopped) return
        misses = data.running ? 0 : misses + 1
        if (misses < MISSES) return
        // 서버에 실행이 없다: 남은 스트림 연결을 끊고 실행 중 표시를 끈다
        stopped = true
        if (!releaseStream(conversationId)) useAgentStore.getState().setRunning(false)
        await new Promise((res) => window.setTimeout(res, 300)) // 끊은 요청이 정리될 시간
        const r = await chatApi.getMessages(conversationId)
        if (!isStreaming(conversationId)) useChatStore.getState().setMessages(conversationId, r.data as Message[])
      } catch {
        // 네트워크 오류는 다음 주기에 다시 확인한다
      }
    }
    const id = window.setInterval(tick, INTERVAL_MS)
    return () => {
      stopped = true
      window.clearInterval(id)
    }
  }, [conversationId, running])
}

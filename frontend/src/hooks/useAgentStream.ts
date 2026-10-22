import { useCallback } from 'react'
import { chatApi } from '../api/chat'
import { useAuthStore } from '../store/authStore'
import { useAgentStore } from '../store/agentStore'
import { useChatStore } from '../store/chatStore'
import type { AgentStreamEvent } from '../types/agent'
import type { Attachment, Message } from '../types/chat'

let stepCounter = 0
function nextStepId() {
  return `step-${Date.now()}-${++stepCounter}`
}

// 대화별 진행 중인 요청의 AbortController (취소 시 연결을 끊는 데 사용)
const controllers = new Map<string, AbortController>()
const CANCEL_NOTE = '_(사용자가 실행을 중단했습니다)_'

const MESSAGE_RENDERED_TOOLS = new Set(['create_widget', 'todo', 'form_ask_user', 'manage_schedule'])
const SANDBOX_TOOLS = new Set([
  'code_executor', 'file_manager', 'shell_executor',
  'write_file', 'edit_file', 'delete_file', 'download_file', 'exec_command',
])

export function useAgentStream(conversationId: string) {
  const { token } = useAuthStore()
  const { setRunning, addStep, appendToken, clearSteps, triggerWorkspaceRefresh } = useAgentStore()
  const { addMessage, updateLastAssistantMessage, appendStepToLastAssistantMessage, setLastAssistantMemorySaved } = useChatStore()

  const sendMessage = useCallback(
    async (content: string, attachments: Attachment[] = []) => {
      clearSteps()
      setRunning(true)

      const userMsg: Message = {
        id: `user-${Date.now()}`,
        conversation_id: conversationId,
        role: 'user',
        content,
        agent_steps: [],
        tool_calls: [],
        attachments,
        created_at: new Date().toISOString(),
      }
      addMessage(conversationId, userMsg)

      const assistantMsg: Message = {
        id: `assistant-${Date.now()}`,
        conversation_id: conversationId,
        role: 'assistant',
        content: '',
        agent_steps: [],
        tool_calls: [],
        created_at: new Date().toISOString(),
      }
      addMessage(conversationId, assistantMsg)

      const controller = new AbortController()
      controllers.set(conversationId, controller)
      let fullContent = ''
      try {
        const response = await fetch(
          `/api/chat/conversations/${conversationId}/messages`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              content,
              attachments,
              // 예약 도구의 기본 시간대와 '현재 시각' 안내에 쓴다
              timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            }),
            signal: controller.signal,
          }
        )

        if (!response.ok) {
          // 예: 409 (이 대화에서 이미 실행 중), 400 (잘못된 첨부)
          let detail = '요청을 처리하지 못했습니다.'
          try {
            const body = await response.json()
            if (typeof body?.detail === 'string') detail = body.detail
          } catch {
            // JSON 이 아니면 기본 문구 사용
          }
          updateLastAssistantMessage(conversationId, `⚠️ ${detail}`)
          return
        }

        const reader = response.body?.getReader()
        const decoder = new TextDecoder()

        while (reader) {
          const { done, value } = await reader.read()
          if (done) break
          const chunk = decoder.decode(value)
          const lines = chunk.split('\n')
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const event: AgentStreamEvent = JSON.parse(line.slice(6))
              if (event.type === 'token' && event.content) {
                fullContent += event.content
                appendToken(event.content)
                updateLastAssistantMessage(conversationId, fullContent)
              } else if (
                event.type === 'thought' ||
                event.type === 'tool_call' ||
                event.type === 'tool_result'
              ) {
                addStep({
                  id: nextStepId(),
                  type: event.type,
                  content: event.content,
                  tool: event.tool,
                  input: event.input,
                  output: event.output,
                  timestamp: new Date().toISOString(),
                })
                // 위젯·할 일·질문 폼은 응답 말풍선 안에 바로 그리기 위해 메시지에도 스텝을 붙인다
                if (
                  event.tool &&
                  ((event.type === 'tool_result' && MESSAGE_RENDERED_TOOLS.has(event.tool)) ||
                    (event.type === 'tool_call' && event.tool === 'form_ask_user'))
                ) {
                  appendStepToLastAssistantMessage(conversationId, {
                    type: event.type,
                    tool: event.tool,
                    input: event.input,
                    output: event.output,
                  })
                }
                // 샌드박스 도구 결과 후 워크스페이스 파일 목록 갱신
                if (event.type === 'tool_result' && event.tool && SANDBOX_TOOLS.has(event.tool)) {
                  triggerWorkspaceRefresh()
                }
              } else if (event.type === 'cancelled') {
                // 서버가 실행을 중단함: 지금까지의 응답 뒤에 중단 안내를 붙인다 (서버에 저장된 내용과 같다)
                fullContent += (fullContent ? '\n\n' : '') + CANCEL_NOTE
                updateLastAssistantMessage(conversationId, fullContent)
              } else if (event.type === 'done') {
                // 응답은 끝났다. 서버가 메모리 추출을 이어서 하는 동안에도 입력을 막지 않는다
                setRunning(false)
              } else if (event.type === 'memory_saved' && event.items?.length) {
                setLastAssistantMemorySaved(conversationId, event.items)
              } else if (event.type === 'error') {
                const friendlyMsg = '비정상적인 에러 발생으로 잠시후에 다시 시도해주세요.'
                updateLastAssistantMessage(conversationId, friendlyMsg)
              }
            } catch {}
          }
        }
      } catch (e) {
        // 취소 API 가 늦거나 실패해 연결을 직접 끊은 경우
        if ((e as Error)?.name !== 'AbortError') throw e
        if (!fullContent.endsWith(CANCEL_NOTE)) {
          fullContent += (fullContent ? '\n\n' : '') + CANCEL_NOTE
          updateLastAssistantMessage(conversationId, fullContent)
        }
      } finally {
        if (controllers.get(conversationId) === controller) controllers.delete(conversationId)
        setRunning(false)
      }
    },
    [conversationId, token, clearSteps, setRunning, addStep, appendToken, addMessage, updateLastAssistantMessage, appendStepToLastAssistantMessage, setLastAssistantMemorySaved, triggerWorkspaceRefresh]
  )

  /** 실행 중인 에이전트를 중단한다. 서버가 `cancelled` 이벤트로 스트림을 끝내고, 응답이 없으면 연결을 직접 끊는다. */
  const cancelRun = useCallback(async () => {
    const controller = controllers.get(conversationId)
    try {
      await chatApi.cancelRun(conversationId)
    } catch {
      controller?.abort() // 서버가 실행 중인 작업을 찾지 못함(404) 등
      return
    }
    setTimeout(() => controller?.abort(), 3000) // 서버 응답이 늦을 때를 대비한 안전장치
  }, [conversationId])

  return { sendMessage, cancelRun }
}

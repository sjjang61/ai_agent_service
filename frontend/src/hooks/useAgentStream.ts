import { useCallback } from 'react'
import { useAuthStore } from '../store/authStore'
import { useAgentStore } from '../store/agentStore'
import { useChatStore } from '../store/chatStore'
import type { AgentStreamEvent } from '../types/agent'
import type { Message } from '../types/chat'

let stepCounter = 0
function nextStepId() {
  return `step-${Date.now()}-${++stepCounter}`
}

const MESSAGE_RENDERED_TOOLS = new Set(['create_widget', 'todo', 'form_ask_user'])
const SANDBOX_TOOLS = new Set([
  'code_executor', 'file_manager', 'shell_executor',
  'write_file', 'edit_file', 'delete_file', 'download_file', 'exec_command',
])

export function useAgentStream(conversationId: string) {
  const { token } = useAuthStore()
  const { setRunning, addStep, appendToken, clearSteps, triggerWorkspaceRefresh } = useAgentStore()
  const { addMessage, updateLastAssistantMessage, appendStepToLastAssistantMessage } = useChatStore()

  const sendMessage = useCallback(
    async (content: string) => {
      clearSteps()
      setRunning(true)

      const userMsg: Message = {
        id: `user-${Date.now()}`,
        conversation_id: conversationId,
        role: 'user',
        content,
        agent_steps: [],
        tool_calls: [],
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

      try {
        const response = await fetch(
          `/api/chat/conversations/${conversationId}/messages`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ content }),
          }
        )

        const reader = response.body?.getReader()
        const decoder = new TextDecoder()
        let fullContent = ''

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
              } else if (event.type === 'error') {
                const friendlyMsg = '비정상적인 에러 발생으로 잠시후에 다시 시도해주세요.'
                updateLastAssistantMessage(conversationId, friendlyMsg)
              }
            } catch {}
          }
        }
      } finally {
        setRunning(false)
      }
    },
    [conversationId, token, clearSteps, setRunning, addStep, appendToken, addMessage, updateLastAssistantMessage, appendStepToLastAssistantMessage, triggerWorkspaceRefresh]
  )

  return { sendMessage }
}

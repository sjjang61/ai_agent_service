export type AgentEventType = 'thought' | 'tool_call' | 'tool_result' | 'token' | 'done' | 'error'

export interface AgentStreamEvent {
  type: AgentEventType
  content?: string
  tool?: string
  input?: unknown
  output?: string
  success?: boolean
  message_id?: string
  message?: string
}

export interface AgentStep {
  id: string
  type: 'thought' | 'tool_call' | 'tool_result'
  content?: string
  tool?: string
  input?: unknown
  output?: string
  timestamp: string
}

/** step 선택 시 오른쪽 패널에 전달하는 공통 타입 */
export interface SelectedStepDetail {
  id: string
  type: 'thought' | 'tool_call' | 'tool_result'
  tool?: string
  content?: string
  input?: unknown
  output?: string
}

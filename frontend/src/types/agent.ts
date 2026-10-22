export type AgentEventType = 'thought' | 'tool_call' | 'tool_result' | 'token' | 'done' | 'error' | 'cancelled' | 'memory_saved'

/** 대화에서 자동으로 저장된 메모리 항목 */
export interface MemorySavedItem {
  key: string
  value: string
  /** semantic 사실 / procedural 작업 방식 / episodic 사례 / short 단기 */
  memory_type?: 'semantic' | 'procedural' | 'episodic' | 'short'
  scope?: 'long' | 'short' // 이전에 저장된 메시지와의 호환
  action: 'added' | 'updated'
}

export interface AgentStreamEvent {
  type: AgentEventType
  content?: string
  tool?: string
  input?: unknown
  output?: string
  success?: boolean
  message_id?: string
  message?: string
  items?: MemorySavedItem[]
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

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
  /** 호출 식별자 (같은 도구가 동시에 여러 번 돌 때 호출과 결과를 정확히 짝짓는다) */
  call_id?: string
  /** 팀원이 한 호출이면 그 팀원 이름 (위임 작업 아래에 묶는다) */
  agent?: string
}

export interface AgentStep {
  id: string
  type: 'thought' | 'tool_call' | 'tool_result'
  content?: string
  tool?: string
  input?: unknown
  output?: string
  callId?: string
  agent?: string
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

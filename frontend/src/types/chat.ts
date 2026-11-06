import type { MemorySavedItem } from './agent'
export interface Conversation {
  id: string
  title: string
  llm_provider: string
  model_name: string
  agent_id?: string | null
  agent_name?: string | null
  agent_icon?: string | null
  agent_version?: number | null
  is_test?: boolean
  /** 스페이스에서 시작한 대화 — 사용자 공용 sandbox 를 쓴다 */
  space_id?: string | null
  created_at: string
  updated_at: string
}

export interface AgentStepData {
  type: string
  content?: string
  tool?: string
  input?: unknown
  output?: string
}

export interface Attachment {
  name: string
  path: string
  size: number
  kind?: 'file' | 'folder'
  file_count?: number
}

/** 질문에 붙이는 참조 자료 (스페이스 페이지 / 이전 대화) */
export interface Reference {
  type: 'page' | 'conversation'
  id: string
  title: string
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  agent_steps: AgentStepData[]
  tool_calls: unknown[]
  attachments?: Attachment[]
  references?: Reference[]
  memory_saved?: MemorySavedItem[]
  /** 이번 요청의 사용량 */
  usage?: MessageUsage | null
  /** 이어서 물어볼 만한 추천 질문 */
  suggestions?: string[]
  created_at: string
}

export interface MessageUsage {
  input_tokens: number
  output_tokens: number
  /** LLM 호출 횟수 */
  requests: number
  elapsed_seconds: number
  /** 예상 비용(USD, 캐시 할인 미반영). 단가를 모르는 모델이면 없음 */
  cost_usd?: number | null
  /** 응답이 끝난 시각 (UTC ISO) */
  finished_at: string
}

export interface SearchSnippet {
  message_id: string
  role: string
  text: string
  created_at: string
}

export interface SearchResult {
  conversation_id: string
  title: string
  updated_at: string | null
  /** 제목에서 일치했는지 */
  title_match: boolean
  snippets: SearchSnippet[]
}

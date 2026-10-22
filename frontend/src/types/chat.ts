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
  created_at: string
}

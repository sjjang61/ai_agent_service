import type { MemorySavedItem } from './agent'
export interface Conversation {
  id: string
  title: string
  llm_provider: string
  model_name: string
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
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  agent_steps: AgentStepData[]
  tool_calls: unknown[]
  attachments?: Attachment[]
  memory_saved?: MemorySavedItem[]
  created_at: string
}

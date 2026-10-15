export type MemoryCategory = 'preference' | 'fact' | 'instruction' | 'general'
export type MemorySource = 'manual' | 'auto_extracted' | 'agent'

export interface Memory {
  id: string
  category: MemoryCategory
  key: string
  value: string
  tags: string[]
  source: MemorySource
  importance: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface MemoryCreate {
  category?: MemoryCategory
  key: string
  value: string
  tags?: string[]
  importance?: number
}

export interface MemoryUpdate {
  category?: MemoryCategory
  value?: string
  tags?: string[]
  importance?: number
  is_active?: boolean
}

export interface MemorySearchParams {
  query?: string
  category?: MemoryCategory
  min_importance?: number
  limit?: number
  offset?: number
}

export interface ShortTermMemory {
  conversation_id: string
  memories: Record<string, string>
}

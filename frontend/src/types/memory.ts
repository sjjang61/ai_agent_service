export type MemoryCategory = 'preference' | 'fact' | 'instruction' | 'general'
/** semantic: 안정된 사실 / procedural: 앞으로 따를 작업 방식 / episodic: 특정 시점의 사건·해결 사례 */
export type MemoryType = 'semantic' | 'procedural' | 'episodic'

export interface EpisodeDetail {
  situation: string
  resolution: string
  outcome: string
}

export type MemorySource = 'manual' | 'auto_extracted' | 'agent'

export interface Memory {
  id: string
  category: MemoryCategory
  memory_type: MemoryType
  occurred_at: string | null
  detail: EpisodeDetail | null
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
  memory_type?: MemoryType
  occurred_at?: string
  detail?: EpisodeDetail
  category?: MemoryCategory
  key: string
  value: string
  tags?: string[]
  importance?: number
}

export interface MemoryUpdate {
  memory_type?: MemoryType
  occurred_at?: string
  detail?: EpisodeDetail
  category?: MemoryCategory
  value?: string
  tags?: string[]
  importance?: number
  is_active?: boolean
}

export interface MemorySearchParams {
  query?: string
  category?: MemoryCategory
  memory_type?: MemoryType
  min_importance?: number
  limit?: number
  offset?: number
}

export interface ShortTermMemory {
  conversation_id: string
  memories: Record<string, string>
}

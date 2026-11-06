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
  /** 유효기간 끝(UTC). 지나면 사라진다. 없으면 영구 */
  expires_at?: string | null
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

/** 전체 대화방의 단기 메모리 한 항목 */
export interface ShortTermItem {
  conversation_id: string
  conversation_title: string | null
  key: string
  value: string
  /** 남은 유지 시간(초). 없으면 null */
  expires_in_seconds: number | null
}

export interface ShortRef {
  conversation_id: string
  key: string
}

export interface ShortGroup {
  title: string
  items: ShortRef[]
}

export interface MergedItem {
  key: string
  value: string
}

export interface ShortMergePreview {
  target_conversation_id: string
  target_conversation_title: string | null
  merged: MergedItem[]
  source_count: number
  conversation_count: number
}

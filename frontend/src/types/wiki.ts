export type WikiCategory = 'general' | 'work' | 'learning' | 'reference'

export interface WikiEntry {
  id: string
  title: string
  content: string
  category: WikiCategory
  tags: string[]
  source_message_id?: string
  source_conversation_id?: string
  created_at: string
  updated_at: string
}

export interface WikiEntryCreate {
  title: string
  content: string
  category?: WikiCategory
  tags?: string[]
  source_message_id?: string
  source_conversation_id?: string
}

export interface WikiEntryUpdate {
  title?: string
  content?: string
  category?: WikiCategory
  tags?: string[]
}

export interface WikiSearchParams {
  query?: string
  category?: WikiCategory
  tags?: string[]
  limit?: number
  offset?: number
}

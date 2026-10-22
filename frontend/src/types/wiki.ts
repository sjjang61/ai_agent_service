export type WikiCategory = 'general' | 'work' | 'learning' | 'reference'

export interface WikiLinkRef {
  id: string
  title: string
}

export interface WikiEntry {
  id: string
  title: string
  content: string
  category: WikiCategory
  tags: string[]
  summary?: string | null
  source_text?: string | null
  links?: WikiLinkRef[] // 이 문서가 연결한 문서
  backlinks?: WikiLinkRef[] // 이 문서를 연결한 문서
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
  summary?: string
  source_text?: string
  links?: string[]
  source_message_id?: string
  source_conversation_id?: string
}

export interface WikiEntryUpdate {
  title?: string
  content?: string
  category?: WikiCategory
  tags?: string[]
  summary?: string
}

/** 선택한 텍스트를 AI 가 정리한 위키 문서 초안 */
export interface WikiDraft {
  title: string
  summary: string
  content: string
  category: WikiCategory
  tags: string[]
  /** 같은 주제의 기존 문서가 있어 그 문서에 합친 결과일 때 */
  merge_into?: WikiLinkRef | null
  related: WikiLinkRef[]
}

export interface WikiMergeRequest {
  content: string
  summary?: string
  tags: string[]
  new_source_text?: string
  add_links: string[]
}

export type WikiLintType = 'duplicate' | 'stale' | 'orphan' | 'broken_link' | 'no_summary'

export interface WikiLintIssue {
  type: WikiLintType
  message: string
  entries: WikiLinkRef[]
}

export interface WikiLintReport {
  total: number
  issues: WikiLintIssue[]
}

export interface WikiSearchParams {
  query?: string
  category?: WikiCategory
  tags?: string[]
  limit?: number
  offset?: number
}

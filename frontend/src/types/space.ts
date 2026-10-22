export interface Space {
  id: string
  name: string
  page_count: number
}

export interface PageSummary {
  id: string
  title: string
  snippet: string
  space_id: string | null
  is_favorite: boolean
  deleted_at: string | null
  created_at: string
  updated_at: string
}

export interface PageDetail extends PageSummary {
  content: string
}

export interface PageUpdate {
  title?: string
  content?: string
  is_favorite?: boolean
  space_id?: string
  clear_space?: boolean
}

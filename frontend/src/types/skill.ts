export interface Skill {
  id: string
  name: string
  description: string | null
  source_url: string
  is_active: boolean
  created_at: string
  plugin_id: string | null
  plugin_name: string | null
}

export interface Plugin {
  id: string
  name: string
  description: string | null
  version: string | null
  source_url: string
  is_active: boolean
  skill_names: string[]
  created_at: string
}

export interface SkillCreateInput {
  name: string
  description: string
  content: string
}

export interface Skill {
  id: string
  name: string
  description: string | null
  source_url: string
  is_active: boolean
  created_at: string
  plugin_id: string | null
  plugin_name: string | null
  /** builtin: sandbox 가 만들어질 때 자동 설치 / custom: 자동 설치하지 않고 필요할 때(load_skill) 설치 */
  skill_type: SkillType
}

export type SkillType = 'builtin' | 'custom'

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
  skill_type?: SkillType
}

export interface SkillFileInfo {
  path: string
  size: number
}

export interface SkillDetail extends Skill {
  files: SkillFileInfo[]
  truncated: boolean
}

export interface SkillFileContent {
  path: string
  size: number
  binary: boolean
  truncated: boolean
  content: string
}

export interface SkillTranslation {
  path: string
  content: string
  truncated: boolean
  /** 저장된 번역 기록을 불러온 것인지 (AI 호출 없음) */
  cached: boolean
  translated_at: string | null
}

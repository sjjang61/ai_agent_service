/** 커스텀 에이전트 (백엔드 schemas/agent.py 와 같은 구조) */
export interface AgentConfig {
  prompt: { instructions: string; starters: string[] }
  model: { llm_provider: string | null; model: string | null; max_iterations: number | null }
  tools: { mode: 'all' | 'selected'; allow: string[] }
  skills: { mode: 'all' | 'selected' | 'none'; names: string[] }
  mcp: { mode: 'all' | 'selected' | 'none'; servers: { name: string; allowed_tools: string[] | null }[] }
  memory: { enabled: boolean }
  team: { mode: 'default' | 'custom' | 'none'; members: SubAgent[] }
}

export interface SubAgent {
  name: string
  role: string
  instructions: string
  tools: string[]
}

export interface ValidationIssue {
  level: 'error' | 'warning'
  path: string
  message: string
}

export interface CustomAgentSummary {
  id: string
  name: string
  description: string
  icon: string
  published_version: number | null
  has_unpublished_changes: boolean
  starters: string[]
  updated_at: string
}

export interface CustomAgent {
  id: string
  name: string
  description: string
  icon: string
  config: AgentConfig
  published_version: number | null
  published_at: string | null
  has_unpublished_changes: boolean
  created_at: string
  updated_at: string
}

export interface SaveResult {
  agent: CustomAgent
  issues: ValidationIssue[]
}

export interface AgentVersion {
  id: string
  version: number
  note: string
  config: AgentConfig
  created_at: string
  is_current: boolean
}

export interface CatalogTool {
  name: string
  description: string
  group: string
  risk: 'read' | 'write' | 'exec'
}

export interface Catalog {
  tools: CatalogTool[]
  skills: { name: string; description: string | null; is_active: boolean }[]
  mcp_servers: { name: string; display_name: string; transport: string; tools: string[] }[]
  llm_providers: string[]
}

export const defaultConfig = (): AgentConfig => ({
  prompt: { instructions: '', starters: [] },
  model: { llm_provider: null, model: null, max_iterations: null },
  tools: { mode: 'all', allow: [] },
  skills: { mode: 'all', names: [] },
  mcp: { mode: 'all', servers: [] },
  memory: { enabled: true },
  team: { mode: 'default', members: [] },
})

import apiClient from './client'

/** 분야: 이 분야 작업에 필요한 입력값과 표준 단계. 사이트의 구조화가 이 키를 따른다. */
export interface VerticalInputDef { key: string; label: string; required: boolean; format: string; example: string }
export interface VerticalFlowStep { key: string; title: string; desc: string; write: boolean }
export interface VerticalSpec { inputs: VerticalInputDef[]; flow: VerticalFlowStep[]; sample: Record<string, string> }

/** 사이트: 진입 주소, 메뉴 지도, 입력값별 입력 방법, 단계별 동작, 멈출 지점 */
export interface SiteSpec {
  entry: { label: string; url: string }[]
  menus: { name: string; path: string; url: string }[]
  inputs: Record<string, { how: string; param: string }>
  flow: { key: string; how: string; url: string; skip?: boolean }[]
  stop_point: string
}

export const emptyVerticalSpec = (): VerticalSpec => ({ inputs: [], flow: [], sample: {} })
export const emptySiteSpec = (): SiteSpec => ({ entry: [], menus: [], inputs: {}, flow: [], stop_point: '' })
/** 서버는 비어 있으면 {} 를 주므로 빠진 항목을 채워 쓴다 */
export const verticalSpecOf = (s?: Partial<VerticalSpec> | null): VerticalSpec => ({ ...emptyVerticalSpec(), ...(s ?? {}) })
export const siteSpecOf = (s?: Partial<SiteSpec> | null): SiteSpec => ({ ...emptySiteSpec(), ...(s ?? {}) })

/** 카테고리(상위 분류): 카테고리 > 분야(상세 카테고리) > 사이트 */
export interface SiteCategory { key: string; name: string }

export interface SiteVertical {
  key: string
  name: string
  category: string | null
  keywords: string
  stop_words: string
  stop_urls: string
  body: string
  checklist: string
  spec: Partial<VerticalSpec>
  source: string
  version: number
  updated_at: string | null
  site_count: number
  md: string
}

export type SiteStatus = 'verified' | 'draft' | 'stale'

export interface SiteProfile {
  id: string
  name: string
  vertical: string | null
  /** 분야가 없는 사이트의 카테고리 (분야가 있으면 분야의 카테고리를 따른다) */
  category: string | null
  domains: string
  aliases: string
  body: string
  spec: Partial<SiteSpec>
  status: SiteStatus
  verified_at: string | null
  enabled: boolean
  source: string
  version: number
  updated_at: string | null
  is_stale: boolean
  md: string
}

export interface SiteProfiles {
  categories: SiteCategory[]
  verticals: SiteVertical[]
  sites: SiteProfile[]
  stale_days: number
}

export type VerticalInput = Pick<SiteVertical, 'name' | 'category' | 'keywords' | 'stop_words' | 'stop_urls' | 'body' | 'checklist'> & { key?: string; version?: number; spec: VerticalSpec }
export type SiteInput = Pick<SiteProfile, 'name' | 'domains' | 'aliases' | 'body' | 'status' | 'enabled'> & {
  spec: SiteSpec
  vertical: string | null
  /** 보내지 않으면 서버가 지금 값을 유지한다 */
  category?: string | null
  verified_at: string | null
  version?: number
}

export interface Revision {
  id: string
  version: number
  source: 'seed' | 'ui' | 'analysis' | 'restore' | string
  author: string | null
  created_at: string | null
  snapshot: Record<string, unknown>
}

export interface AnalysisStep {
  id: string | null
  action: string
  desc: string
  url: string
  ok: boolean | null
  brief: string
  t0: number | null
  t1: number | null
}

export interface FlowResult {
  key: string
  title: string
  write: boolean
  status: 'reached' | 'failed' | 'skipped' | 'missing' | 'untested' | 'excluded'
  note: string
}

export interface VerifyResult {
  passed: boolean
  success: boolean
  summary: string
  issues: string[]
  steps: number
  failed_steps: number
  loop_blocks: number
  seconds: number
  flow?: FlowResult[]
}

export interface AnalysisRun {
  id: string
  mode: 'analyze' | 'verify'
  name: string
  vertical: string | null
  start_url: string
  scenario: string
  status: 'running' | 'succeeded' | 'failed' | 'cancelled'
  browser_run: string | null
  steps: AnalysisStep[]
  draft_body: string | null
  draft_spec: Partial<SiteSpec> | null
  inputs: Record<string, string> | null
  captcha_handoff: boolean
  clean_session: boolean
  result: VerifyResult | null
  answer: string | null
  error: string | null
  base_run_id: string | null
  created_at: string | null
  finished_at: string | null
}

export interface AnalysisInput {
  mode: 'analyze' | 'verify'
  name: string
  vertical: string | null
  start_url: string
  scenario: string
  draft_body?: string
  draft_spec?: SiteSpec
  inputs?: Record<string, string>
  captcha_handoff?: boolean
  clean_session?: boolean
  current_body?: string
  base_run_id?: string
}

export interface SiteCommon { body: string; version: number; source: string; updated_by: string | null; updated_at: string | null }

export const siteProfilesApi = {
  getCommon: () => apiClient.get<SiteCommon>('/site-profiles/common'),
  updateCommon: (data: { body: string; version?: number }) => apiClient.put<SiteCommon>('/site-profiles/common', data),
  list: () => apiClient.get<SiteProfiles>('/site-profiles'),
  createVertical: (data: VerticalInput) => apiClient.post<SiteVertical>('/site-profiles/verticals', data),
  updateVertical: (key: string, data: VerticalInput) => apiClient.put<SiteVertical>(`/site-profiles/verticals/${key}`, data),
  deleteVertical: (key: string) => apiClient.delete(`/site-profiles/verticals/${key}`),
  createSite: (data: SiteInput) => apiClient.post<SiteProfile>('/site-profiles/sites', data),
  updateSite: (id: string, data: SiteInput) => apiClient.put<SiteProfile>(`/site-profiles/sites/${id}`, data),
  deleteSite: (id: string) => apiClient.delete(`/site-profiles/sites/${id}`),
  preview: (data: SiteInput) => apiClient.post<{ text: string }>('/site-profiles/sites/preview', data),
  siteRevisions: (id: string) => apiClient.get<Revision[]>(`/site-profiles/sites/${id}/revisions`),
  restoreSite: (id: string, revId: string) => apiClient.post<SiteProfile>(`/site-profiles/sites/${id}/revisions/${revId}/restore`),
  verticalRevisions: (key: string) => apiClient.get<Revision[]>(`/site-profiles/verticals/${key}/revisions`),
  restoreVertical: (key: string, revId: string) => apiClient.post<SiteVertical>(`/site-profiles/verticals/${key}/revisions/${revId}/restore`),
  startAnalysis: (data: AnalysisInput) => apiClient.post<AnalysisRun>('/site-profiles/analysis/runs', data),
  analysisRuns: (name?: string) => apiClient.get<AnalysisRun[]>('/site-profiles/analysis/runs', { params: { name, limit: 8 } }),
  analysisRun: (id: string) => apiClient.get<AnalysisRun>(`/site-profiles/analysis/runs/${id}`),
  cancelAnalysis: (id: string) => apiClient.post<AnalysisRun>(`/site-profiles/analysis/runs/${id}/cancel`),
}

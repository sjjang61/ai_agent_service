import apiClient from './client'
import { getServerUrl } from '../config/server'
import { driveApi } from './drive'

export interface FnInfo {
  enabled: boolean
  allowed: boolean
  is_admin: boolean
  runtimes: string[]
  allow_network: boolean
  limits: {
    package_mb: number; timeout_default: number; timeout_max: number; memory_default_mb: number; memory_max_mb: number
    event_kb: number; result_kb: number; log_kb: number; sync_wait_seconds: number; retention_days: number; runs_per_day: number
  }
}

export type RunStatus = 'queued' | 'starting' | 'running' | 'succeeded' | 'failed' | 'timeout' | 'cancelled' | 'rejected'

export interface FnSummary {
  id: string
  name: string
  description: string
  runtime: string
  latest_version: number
  disabled: boolean
  disabled_reason: string | null
  created_at: string | null
  updated_at: string | null
  last_run?: { status: RunStatus | null; queued_at: string | null }
}

export interface FnVersion {
  version: number
  sha256: string
  size_bytes: number
  unpacked_bytes: number
  file_count: number
  config: { runtime: string; handler: string; timeout_seconds: number; memory_mb: number; allow_network: boolean; env: Record<string, string> }
  source: string
  source_ref: { drive_path?: string } | null
  created_at: string | null
}

export interface FnDetail extends FnSummary {
  versions: FnVersion[]
  aliases: Record<string, number>
  secrets: string[]
}

export interface RunSummary {
  id: string
  function_id: string
  version: number
  trigger: string
  status: RunStatus
  queued_at: string | null
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  cold_start_ms: number | null
  exit_code: number | null
  error: { type: string; message: string } | null
  cancel_requested: boolean
  attempt: number
}

export interface RunDetail extends RunSummary {
  input: unknown
  result: unknown
  log_truncated: boolean
  log_size: number
}

export type ScheduleType = 'once' | 'interval' | 'daily' | 'weekdays' | 'weekly' | 'monthly'

export interface FnTrigger {
  id: string
  function_id: string
  kind: 'schedule' | 'webhook'
  name: string
  ref: string
  enabled: boolean
  last_run_at: string | null
  last_run_id: string | null
  last_status: string | null
  created_at: string | null
  // 예약
  schedule_type?: ScheduleType
  schedule_time?: string | null
  weekdays?: number[] | null
  day_of_month?: number | null
  interval_hours?: number | null
  timezone?: string | null
  next_run_at?: string | null
  consecutive_failures?: number
  description?: string
  // 웹훅 (token/path 는 만들거나 재발급한 응답에만 들어 있다)
  last_called_at?: string | null
  token?: string
  path?: string | null
}

export interface TriggerCreate {
  kind: 'schedule' | 'webhook'
  name?: string
  ref?: string
  schedule_type?: ScheduleType
  schedule_time?: string
  weekdays?: number[]
  day_of_month?: number
  interval_hours?: number
  run_at?: string
  timezone?: string
}

export const ACTIVE: RunStatus[] = ['queued', 'starting', 'running']

export const STATUS_LABEL: Record<RunStatus, string> = {
  queued: '대기 중', starting: '시작 중', running: '실행 중', succeeded: '성공', failed: '실패', timeout: '시간 초과', cancelled: '취소됨', rejected: '거부됨',
}

export const functionsApi = {
  info: () => apiClient.get<FnInfo>('/functions/info').then((r) => r.data),
  list: () => apiClient.get<{ functions: FnSummary[] }>('/functions').then((r) => r.data.functions),
  get: (id: string) => apiClient.get<FnDetail>(`/functions/${id}`).then((r) => r.data),
  create: (name: string, description: string, driveNodeId: string) =>
    apiClient.post<FnSummary>('/functions', { name, description, drive_node_id: driveNodeId }).then((r) => r.data),
  updateDescription: (id: string, description: string) => apiClient.put<FnSummary>(`/functions/${id}`, { description }).then((r) => r.data),
  remove: (id: string) => apiClient.delete(`/functions/${id}`).then((r) => r.data),
  addVersion: (id: string, driveNodeId: string) =>
    apiClient.post<{ version: FnVersion; created: boolean }>(`/functions/${id}/versions`, { drive_node_id: driveNodeId }).then((r) => r.data),
  setAlias: (id: string, alias: string, version: number) => apiClient.put(`/functions/${id}/aliases/${encodeURIComponent(alias)}`, { version }).then((r) => r.data),
  removeAlias: (id: string, alias: string) => apiClient.delete(`/functions/${id}/aliases/${encodeURIComponent(alias)}`).then((r) => r.data),
  putSecret: (id: string, key: string, value: string) => apiClient.put(`/functions/${id}/secrets/${encodeURIComponent(key)}`, { value }).then((r) => r.data),
  removeSecret: (id: string, key: string) => apiClient.delete(`/functions/${id}/secrets/${encodeURIComponent(key)}`).then((r) => r.data),
  /** wait=true 면 서버가 결과까지 기다려 돌려준다(시간 초과 시 done=false) */
  invoke: (id: string, event: unknown, opts: { ref?: string; wait?: boolean } = {}) =>
    apiClient.post<{ run: RunSummary | RunDetail; done: boolean }>(`/functions/${id}/invoke`, { event, ref: opts.ref, wait: opts.wait ?? false }).then((r) => r.data),
  runs: (params: { function_id?: string; status?: string; limit?: number } = {}) =>
    apiClient.get<{ runs: RunSummary[] }>('/runs', { params }).then((r) => r.data.runs),
  run: (id: string) => apiClient.get<RunDetail>(`/runs/${id}`).then((r) => r.data),
  logs: (id: string) => apiClient.get<{ log: string; next: number; done: boolean; truncated: boolean }>(`/runs/${id}/logs`).then((r) => r.data),
  cancel: (id: string) => apiClient.post<RunSummary>(`/runs/${id}/cancel`).then((r) => r.data),
  triggers: (functionId: string) => apiClient.get<{ triggers: FnTrigger[] }>(`/functions/${functionId}/triggers`).then((r) => r.data.triggers),
  allTriggers: () => apiClient.get<{ triggers: FnTrigger[] }>('/fn-triggers').then((r) => r.data.triggers),
  createTrigger: (functionId: string, body: TriggerCreate) => apiClient.post<FnTrigger>(`/functions/${functionId}/triggers`, body).then((r) => r.data),
  setTriggerEnabled: (id: string, enabled: boolean) => apiClient.patch<FnTrigger>(`/fn-triggers/${id}`, { enabled }).then((r) => r.data),
  removeTrigger: (id: string) => apiClient.delete(`/fn-triggers/${id}`).then((r) => r.data),
  regenerateHook: (id: string) => apiClient.post<FnTrigger>(`/fn-triggers/${id}/regenerate`).then((r) => r.data),
}

/** 웹훅 주소를 외부에서 쓸 수 있는 전체 주소로 만든다 (서버 주소가 따로 설정된 데스크톱 환경도 따른다) */
export function webhookUrl(path: string): string {
  const base = (getServerUrl() || window.location.origin).replace(/\/+$/, '')
  return `${base}${path}`
}

/** 로컬 zip 을 Drive 의 /Functions 폴더에 올리고 노드 id 를 돌려준다 (함수 패키지는 Drive 에서 등록한다) */
export async function uploadPackageToDrive(file: File, onProgress: (ratio: number) => void): Promise<string> {
  const root = await driveApi.list('root', { foldersOnly: true })
  const existing = root.nodes.find((n) => n.name.toLowerCase() === 'functions')
  const folder = existing ?? (await driveApi.createFolder('root', 'Functions'))
  const node = await driveApi.upload(file, folder.id, onProgress).promise
  return node.id
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return '-'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(ms < 10_000 ? 2 : 1)}s`
  return `${Math.floor(ms / 60_000)}m ${Math.round((ms % 60_000) / 1000)}s`
}

import apiClient from './client'

export interface DeployedApp {
  id: string
  name: string
  kind: 'static' | 'server'
  url: string | null
  port: number | null
  status: 'stopped' | 'starting' | 'running' | 'failed'
  error: string | null
  version: number
  visibility: 'private' | 'public'
  /** 공개 앱의 검수 상태: approved(서비스 중) | pending(승인 대기) | rejected | suspended(정지). 비공개는 '' */
  moderation_status: '' | 'approved' | 'pending' | 'rejected' | 'suspended'
  moderation_note: string | null
  title: string | null
  description: string | null
  category: string | null
  tags: string[]
  launch_count: number
  conversation_id: string | null
  artifact_size: number
  last_request_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface ListingInput {
  title: string
  description: string
  category: string
  tags: string[]
  accept_terms: boolean
}

export interface StoreApp {
  id: string
  slug: string
  title: string
  description: string
  category: string
  tags: string[]
  owner_name: string
  version: number
  kind: 'static' | 'server'
  launch_count: number
  listed_at: string | null
  url: string
}

export interface QueueItem extends StoreApp {
  moderation_status: string
  moderation_note: string | null
  reports: number
  reasons: string[]
}

export const appsApi = {
  list: () => apiClient.get<DeployedApp[]>('/apps'),
  info: () => apiClient.get<{ categories: string[] }>('/apps/info'),
  start: (id: string) => apiClient.post<DeployedApp>(`/apps/${id}/start`, null, { timeout: 120000 }),
  stop: (id: string) => apiClient.post<DeployedApp>(`/apps/${id}/stop`),
  remove: (id: string) => apiClient.delete(`/apps/${id}`),
  logs: (id: string, lines = 200) => apiClient.get<{ logs: string }>(`/apps/${id}/logs`, { params: { lines } }),
  /** 앱을 여는 주소. 비공개 앱은 소유자에게 일회용 실행 티켓(60초)이 붙은 주소라서, 열 때마다 새로 받아야 한다. */
  launch: async (id: string) => (await apiClient.post<{ url: string }>(`/apps/${id}/launch`)).data.url,
  publish: (id: string, data: ListingInput) => apiClient.post<DeployedApp>(`/apps/${id}/publish`, data),
  updateListing: (id: string, data: ListingInput) => apiClient.put<DeployedApp>(`/apps/${id}/listing`, data),
  unpublish: (id: string) => apiClient.post<DeployedApp>(`/apps/${id}/unpublish`),
}

export const storeApi = {
  info: () => apiClient.get<{ is_admin: boolean; categories: string[] }>('/store/info'),
  list: (params: { q?: string; category?: string; sort?: 'popular' | 'new' }) => apiClient.get<StoreApp[]>('/store/apps', { params }),
  get: (id: string) => apiClient.get<StoreApp>(`/store/apps/${id}`),
  launch: async (id: string) => (await apiClient.post<{ url: string }>(`/store/apps/${id}/launch`)).data.url,
  report: (id: string, reason: string) => apiClient.post(`/store/apps/${id}/report`, { reason }),
  adminQueue: (status: string) => apiClient.get<QueueItem[]>('/store/admin/queue', { params: { status } }),
  moderate: (id: string, action: 'approve' | 'reject' | 'suspend', note?: string) => apiClient.post(`/store/admin/apps/${id}/moderate`, { action, note }),
}

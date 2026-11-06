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
  require_token: boolean
  conversation_id: string | null
  artifact_size: number
  last_request_at: string | null
  created_at: string | null
  updated_at: string | null
}

export const appsApi = {
  list: () => apiClient.get<DeployedApp[]>('/apps'),
  start: (id: string) => apiClient.post<DeployedApp>(`/apps/${id}/start`, null, { timeout: 120000 }),
  stop: (id: string) => apiClient.post<DeployedApp>(`/apps/${id}/stop`),
  remove: (id: string) => apiClient.delete(`/apps/${id}`),
  logs: (id: string, lines = 200) => apiClient.get<{ logs: string }>(`/apps/${id}/logs`, { params: { lines } }),
}

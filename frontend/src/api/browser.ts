import apiClient from './client'

export interface BrowserProfile {
  has_profile: boolean
  domains: { domain: string; cookies: number }[]
  size_bytes: number
  updated_at: string | null
}

export interface LoginRequest {
  site: string
  url: string
  reason: string
}

export interface BrowserShot {
  path: string
  url: string
  title: string
  t: number
  run: string | null
}

export const browserApi = {
  shots: (conversationId: string | null, run: string, limit = 30) =>
    apiClient.get<BrowserShot[]>('/browser/shots', { params: { conversation_id: conversationId ?? undefined, run, limit } }),
  profile: () => apiClient.get<BrowserProfile>('/browser/profile'),
  deleteProfile: () => apiClient.delete('/browser/profile'),
  deleteDomain: (domain: string) => apiClient.delete(`/browser/profile/domains/${encodeURIComponent(domain)}`),
  loginRequest: (conversationId: string) =>
    apiClient.get<LoginRequest | null>('/browser/login-request', { params: { conversation_id: conversationId } }),
  finishLogin: (conversationId: string, cancelled = false) =>
    apiClient.post('/browser/login-request/done', { conversation_id: conversationId, cancelled }),
}

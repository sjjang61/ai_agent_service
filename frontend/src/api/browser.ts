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
  /** login: 로그인/CAPTCHA 인계, approval: 쓰기 동작 승인 */
  kind?: 'login' | 'approval'
  action?: string
  detail?: string
  /** ask: '이 대화에서 이 사이트는 다시 묻지 않기' 가능, ask_always: 항상 승인 */
  level?: 'ask' | 'ask_always' | ''
  /** true: 데스크톱 앱의 내장 브라우저에서 직접 진행 (라이브 브라우저를 열지 않는다) */
  local?: boolean
  /** 병렬 브라우저 작업이면 어느 작업(사이트)의 요청인지 */
  session?: string
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
  finishLogin: (conversationId: string, cancelled = false, remember = false) =>
    apiClient.post('/browser/login-request/done', { conversation_id: conversationId, cancelled, remember }),
}

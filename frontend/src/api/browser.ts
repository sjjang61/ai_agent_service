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
  /** 데스크톱 로컬 브라우저 스크린샷 이미지 (path 가 local://파일명 인 것) */
  shotImage: (name: string) => apiClient.get<Blob>('/browser/shots/image', { params: { name }, responseType: 'blob' }),
  profile: () => apiClient.get<BrowserProfile>('/browser/profile'),
  /** 일반 Chrome 확장 연결 토큰 (확장 연결에만 쓸 수 있다) */
  extToken: () => apiClient.post<{ token: string; days: number }>('/browser/ext-token'),
  extStatus: () => apiClient.get<{ connected: boolean; enabled: boolean }>('/browser/ext-status'),
  deleteProfile: () => apiClient.delete('/browser/profile'),
  deleteDomain: (domain: string) => apiClient.delete(`/browser/profile/domains/${encodeURIComponent(domain)}`),
  loginRequest: (conversationId: string) =>
    apiClient.get<LoginRequest | null>('/browser/login-request', { params: { conversation_id: conversationId } }),
  finishLogin: (conversationId: string, cancelled = false, remember = false) =>
    apiClient.post('/browser/login-request/done', { conversation_id: conversationId, cancelled, remember }),
}

import apiClient from './client'

export interface ConnectorInfo {
  id: string
  name: string
  description: string
  category: string
  /** account: 계정 로그인(OAuth) */
  connect_kind: 'account'
  connected: boolean
  account_email: string | null
}

export interface ConnectorList {
  /** 서버에 Google OAuth 클라이언트가 설정돼 있는가 */
  configured: boolean
  /** Google Cloud 콘솔의 승인된 리디렉션 URI 에 등록해야 하는 주소 */
  redirect_uri: string
  connectors: ConnectorInfo[]
}

export interface VerifyResult {
  /** valid 정상 | expired 다시 연결 필요 | error 일시 오류 | none 연결 없음 */
  status: 'valid' | 'expired' | 'error' | 'none'
  message: string
  account_email?: string | null
}

export const connectorsApi = {
  list: async () => (await apiClient.get<ConnectorList>('/connectors')).data,
  /** Google 인증 화면 주소 */
  connect: async (id: string) => (await apiClient.post<{ auth_url: string }>(`/connectors/${id}/connect`)).data.auth_url,
  /** 저장된 연결이 지금도 유효한지 Google 에 실제로 확인한다 */
  verify: async () => (await apiClient.post<VerifyResult>('/connectors/verify')).data,
  disconnect: (id: string) => apiClient.delete(`/connectors/${id}`),
}

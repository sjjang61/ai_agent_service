import axios from 'axios'
import { apiUrl } from '../config/server'
import apiClient from './client'

export interface ShareStatus {
  shared: boolean
  token?: string
  path?: string
  message_count?: number
  view_count?: number
  shared_at?: string | null
  expires_at?: string | null
}

export interface SharedMessage {
  role: 'user' | 'assistant'
  content: string
  widgets: import('../types/widget').Widget[]
  created_at: string | null
}

export interface SharedConversation {
  title: string
  messages: SharedMessage[]
  shared_at: string | null
}

/** 공유 링크의 전체 주소. 서비스를 연 주소가 외부에서 열리는 주소가 아니면(예: 데스크톱) VITE_SHARE_BASE_URL 로 정한다 */
export function shareUrl(path: string): string {
  const base = ((import.meta.env.VITE_SHARE_BASE_URL as string | undefined) || window.location.origin).replace(/\/+$/, '')
  return `${base}${path}`
}

export const shareApi = {
  status: (conversationId: string) => apiClient.get<ShareStatus>(`/chat/conversations/${conversationId}/share`),
  /** 처음이면 링크를 만들고, 이미 있으면 같은 주소의 내용을 지금 대화로 갱신한다 */
  share: (conversationId: string) => apiClient.post<ShareStatus>(`/chat/conversations/${conversationId}/share`),
  unshare: (conversationId: string) => apiClient.delete(`/chat/conversations/${conversationId}/share`),
  /** 로그인 없이 읽는다: 로그인 토큰·401 처리가 붙은 apiClient 를 쓰지 않는다 */
  read: (token: string) => axios.get<SharedConversation>(apiUrl(`/api/shared/${encodeURIComponent(token)}`)),
}

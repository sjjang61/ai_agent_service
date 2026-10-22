import apiClient from './client'
import type { ArtifactList, ArtifactPreview } from '../types/artifact'
import type { Attachment } from '../types/chat'

/** 대화방 id 가 있으면 그 대화방의 sandbox, 없으면 사용자 공용 sandbox (스페이스 대화는 서버가 공용으로 연결한다) */
const scope = (conversationId?: string | null) => (conversationId ? { conversation_id: conversationId } : {})

export interface SandboxInstance {
  id: string
  scope: 'shared' | 'conversation'
  conversation_id: string | null
  conversation_title: string | null
  status: string
  last_used_at: string | null
}

export const sandboxApi = {
  getStatus: (conversationId?: string | null) => apiClient.get('/sandbox/status', { params: scope(conversationId) }),
  startSandbox: (conversationId?: string | null) => apiClient.post('/sandbox/start', null, { params: scope(conversationId) }),
  stopSandbox: (conversationId?: string | null) => apiClient.post('/sandbox/stop', null, { params: scope(conversationId) }),
  /** 내 sandbox 전체: 공용 1개 + 대화방별 */
  listInstances: () => apiClient.get<SandboxInstance[]>('/sandbox/instances'),
  stopInstance: (id: string) => apiClient.post(`/sandbox/instances/${id}/stop`),
  deleteInstance: (id: string) => apiClient.delete(`/sandbox/instances/${id}`),
  getWorkspaceTree: (conversationId?: string | null) =>
    apiClient.get<{ files: string[] }>('/sandbox/workspace-tree', { params: scope(conversationId) }),
  getFileContent: (path: string, conversationId?: string | null) =>
    apiClient.get<{ path: string; content: string }>(`/sandbox/files/${path}`, { params: scope(conversationId) }),
  getArtifacts: (hidden = false, conversationId?: string | null) =>
    apiClient.get<ArtifactList>('/sandbox/artifacts', { params: { hidden, ...scope(conversationId) } }),
  previewArtifact: (path: string, conversationId?: string | null) =>
    apiClient.get<ArtifactPreview>('/sandbox/artifacts/preview', { params: { path, ...scope(conversationId) } }),
  /** 파일 원본을 Blob 으로 받는다 (인증 헤더가 필요해서 <a href> 대신 사용) */
  fetchArtifactBlob: (path: string, download = true, conversationId?: string | null) =>
    apiClient.get<Blob>('/sandbox/artifacts/raw', { params: { path, download, ...scope(conversationId) }, responseType: 'blob' }),
  publishArtifact: (path: string, expiresHours?: number, conversationId?: string | null) =>
    apiClient.post<{ url: string; expires_at: string }>(
      '/sandbox/artifacts/publish',
      { path, expires_hours: expiresHours },
      { params: scope(conversationId) }
    ),
  /** 폴더를 통째로 올린다 (paths = 폴더 이름을 포함한 상대 경로). 첨부 하나(kind=folder)로 돌려준다 */
  uploadFolder: (files: File[], paths: string[], onProgress?: (percent: number) => void, conversationId?: string | null) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    paths.forEach((p) => form.append('paths', p))
    if (conversationId) form.append('conversation_id', conversationId)
    return apiClient.post<{ files: Attachment[] }>('/sandbox/uploads/folder', form, {
      headers: { 'Content-Type': undefined },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    })
  },
  /** 채팅 첨부 파일을 그 대화의 sandbox(/workspace/uploads/)에 올린다 (파일 하나씩 호출해 진행·오류를 구분한다) */
  uploadFile: (file: File, onProgress?: (percent: number) => void, conversationId?: string | null) => {
    const form = new FormData()
    form.append('files', file)
    if (conversationId) form.append('conversation_id', conversationId)
    return apiClient.post<{ files: Attachment[] }>('/sandbox/uploads', form, {
      headers: { 'Content-Type': undefined }, // 기본 JSON 헤더를 지워 브라우저가 multipart boundary 를 붙이게 한다
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    })
  },
}

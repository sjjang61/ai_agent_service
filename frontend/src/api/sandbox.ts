import apiClient from './client'
import type { ArtifactList, ArtifactPreview } from '../types/artifact'
import type { Attachment } from '../types/chat'

export const sandboxApi = {
  getStatus: () => apiClient.get('/sandbox/status'),
  startSandbox: () => apiClient.post('/sandbox/start'),
  stopSandbox: () => apiClient.post('/sandbox/stop'),
  getWorkspaceTree: () => apiClient.get<{ files: string[] }>('/sandbox/workspace-tree'),
  getFileContent: (path: string) =>
    apiClient.get<{ path: string; content: string }>(`/sandbox/files/${path}`),
  getArtifacts: (hidden = false) =>
    apiClient.get<ArtifactList>('/sandbox/artifacts', { params: { hidden } }),
  previewArtifact: (path: string) =>
    apiClient.get<ArtifactPreview>('/sandbox/artifacts/preview', { params: { path } }),
  /** 파일 원본을 Blob 으로 받는다 (인증 헤더가 필요해서 <a href> 대신 사용) */
  fetchArtifactBlob: (path: string, download = true) =>
    apiClient.get<Blob>('/sandbox/artifacts/raw', { params: { path, download }, responseType: 'blob' }),
  publishArtifact: (path: string, expiresHours?: number) =>
    apiClient.post<{ url: string; expires_at: string }>('/sandbox/artifacts/publish', {
      path,
      expires_hours: expiresHours,
    }),
  /** 채팅 첨부 파일을 sandbox(/workspace/uploads/)에 올린다 (파일 하나씩 호출해 진행·오류를 구분한다) */
  uploadFile: (file: File, onProgress?: (percent: number) => void) => {
    const form = new FormData()
    form.append('files', file)
    return apiClient.post<{ files: Attachment[] }>('/sandbox/uploads', form, {
      headers: { 'Content-Type': undefined }, // 기본 JSON 헤더를 지워 브라우저가 multipart boundary 를 붙이게 한다
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    })
  },
}

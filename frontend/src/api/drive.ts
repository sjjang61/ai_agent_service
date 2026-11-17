import { apiBase } from '../config/server'
import { useAuthStore } from '../store/authStore'
import apiClient from './client'

export interface DriveNode {
  id: string
  type: 'folder' | 'file'
  name: string
  parent_id: string | null
  size_bytes: number | null
  mime: string | null
  source: 'upload' | 'agent' | 'sandbox' | 'function'
  created_at: string | null
  updated_at: string | null
  trashed_at: string | null
}

export interface DriveListing {
  folder: DriveNode
  path: string
  breadcrumb: { id: string; name: string }[]
  nodes: DriveNode[]
  next_cursor: number | null
}

export type SortKey = 'name' | 'size' | 'updated'

export interface UploadHandle {
  promise: Promise<DriveNode>
  abort: () => void
}

/** 서버가 준 오류 문구(detail). 없으면 대신할 문구 */
export function driveError(e: unknown, fallback: string): string {
  const d = (e as { response?: { data?: { detail?: unknown } }; message?: string })?.response?.data?.detail
  return typeof d === 'string' ? d : fallback
}

export const driveApi = {
  list: (parentId: string, opts: { sort?: SortKey; desc?: boolean; cursor?: number; foldersOnly?: boolean } = {}) =>
    apiClient
      .get<DriveListing>('/drive/nodes', { params: { parent_id: parentId, sort: opts.sort ?? 'name', desc: opts.desc ?? false, cursor: opts.cursor ?? 0, folders_only: opts.foldersOnly ?? false } })
      .then((r) => r.data),
  createFolder: (parentId: string, name: string) => apiClient.post<DriveNode>('/drive/folders', { parent_id: parentId, name }).then((r) => r.data),
  rename: (id: string, name: string) => apiClient.patch<DriveNode>(`/drive/nodes/${id}`, { name }).then((r) => r.data),
  move: (ids: string[], parentId: string) => apiClient.post<{ moved: number }>('/drive/nodes/move', { ids, parent_id: parentId }).then((r) => r.data),
  remove: (ids: string[]) => apiClient.post<{ trashed: number }>('/drive/nodes/delete', { ids }).then((r) => r.data),
  usage: () => apiClient.get<{ used_bytes: number; quota_bytes: number }>('/drive/usage').then((r) => r.data),
  trash: () => apiClient.get<{ nodes: DriveNode[]; retention_days: number }>('/drive/trash').then((r) => r.data),
  restore: (ids: string[]) => apiClient.post('/drive/trash/restore', { ids }).then((r) => r.data),
  purge: (ids: string[]) => apiClient.post('/drive/trash/purge', { ids }).then((r) => r.data),
  /** sandbox 의 파일·폴더를 Drive 로 저장한다 (사본). paths 는 /workspace 기준 */
  importSandbox: (conversationId: string | null | undefined, paths: string[], parentId: string) =>
    apiClient.post<{ saved: DriveNode[]; files: number }>('/drive/import/sandbox', { conversation_id: conversationId ?? null, paths, parent_id: parentId }).then((r) => r.data),
  /** Drive 파일을 채팅 첨부로 쓴다 (sandbox 의 uploads 로 복사). 반환값은 채팅 첨부 형식 */
  attach: (nodeId: string, conversationId?: string | null) =>
    apiClient.post<{ name: string; path: string; size: number }>(`/drive/files/${nodeId}/attach`, { conversation_id: conversationId ?? null }).then((r) => r.data),
  emptyTrash: () => apiClient.post('/drive/trash/empty').then((r) => r.data),

  /** 파일 한 개를 올린다. 본문은 파일 바이트 그대로(raw)이고 진행률·취소를 지원한다 (axios 는 업로드 진행률 취소가 번거로워 XHR 를 쓴다) */
  upload(file: File, parentId: string, onProgress: (ratio: number) => void): UploadHandle {
    const xhr = new XMLHttpRequest()
    const promise = new Promise<DriveNode>((resolve, reject) => {
      const url = `${apiBase()}/drive/files?name=${encodeURIComponent(file.name)}&parent_id=${encodeURIComponent(parentId)}`
      xhr.open('POST', url)
      const token = useAuthStore.getState().token
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      xhr.setRequestHeader('Content-Type', 'application/octet-stream')
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total)
      xhr.onload = () => {
        let body: { detail?: string } & Partial<DriveNode> = {}
        try { body = JSON.parse(xhr.responseText) } catch { /* 본문이 JSON 이 아님 */ }
        if (xhr.status >= 200 && xhr.status < 300) resolve(body as DriveNode)
        else {
          if (xhr.status === 401) useAuthStore.getState().logout()
          reject(new Error(typeof body.detail === 'string' ? body.detail : `업로드하지 못했습니다 (${xhr.status})`))
        }
      }
      xhr.onerror = () => reject(new Error('네트워크 오류로 업로드하지 못했습니다'))
      xhr.onabort = () => reject(new DOMException('취소됨', 'AbortError'))
      xhr.send(file)
    })
    return { promise, abort: () => xhr.abort() }
  },

  /** 인증 헤더가 필요해 링크가 아니라 blob 으로 받아 저장한다 */
  async download(node: DriveNode): Promise<void> {
    const res = await apiClient.get<Blob>(`/drive/files/${node.id}/download`, { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = node.name
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
}

import apiClient from './client'
import type {
  Memory,
  MemoryCreate,
  MemoryUpdate,
  MemorySearchParams,
  ShortGroup,
  ShortMergePreview,
  ShortRef,
  MergedItem,
  ShortTermItem,
  ShortTermMemory,
} from '../types/memory'

export const memoryApi = {
  list: (params?: MemorySearchParams) =>
    apiClient.get<Memory[]>('/memory/', { params }),

  get: (id: string) => apiClient.get<Memory>(`/memory/${id}`),

  create: (data: MemoryCreate) => apiClient.post<Memory>('/memory/', data),

  update: (id: string, data: MemoryUpdate) =>
    apiClient.put<Memory>(`/memory/${id}`, data),

  delete: (id: string) => apiClient.delete(`/memory/${id}`),

  // Short-term memory
  listShortTermAll: () => apiClient.get<ShortTermItem[]>('/memory/short'),

  groupShortTerm: () => apiClient.post<{ groups: ShortGroup[] }>('/memory/short/group', {}, { timeout: 120000 }),

  previewShortMerge: (items: ShortRef[]) =>
    apiClient.post<ShortMergePreview>('/memory/short/merge/preview', { items }, { timeout: 120000 }),

  applyShortMerge: (items: ShortRef[], merged: MergedItem[], target_conversation_id: string) =>
    apiClient.post<{ saved: number; removed: number }>('/memory/short/merge/apply', { items, merged, target_conversation_id }),

  deleteShortTerm: (conversationId: string, key: string) =>
    apiClient.delete(`/memory/short/${conversationId}/${encodeURIComponent(key)}`),

  getShortTerm: (conversationId: string) =>
    apiClient.get<ShortTermMemory>(`/memory/short/${conversationId}`),

  clearShortTerm: (conversationId: string) =>
    apiClient.delete(`/memory/short/${conversationId}`),
}

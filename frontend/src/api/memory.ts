import apiClient from './client'
import type {
  Memory,
  MemoryCreate,
  MemoryUpdate,
  MemorySearchParams,
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
  getShortTerm: (conversationId: string) =>
    apiClient.get<ShortTermMemory>(`/memory/short/${conversationId}`),

  clearShortTerm: (conversationId: string) =>
    apiClient.delete(`/memory/short/${conversationId}`),
}

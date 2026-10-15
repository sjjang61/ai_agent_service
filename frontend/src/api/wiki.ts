import apiClient from './client'
import type {
  WikiEntry,
  WikiEntryCreate,
  WikiEntryUpdate,
  WikiSearchParams,
} from '../types/wiki'

export const wikiApi = {
  list: (params?: WikiSearchParams) =>
    apiClient.get<WikiEntry[]>('/wiki/', { params }),

  get: (id: string) => apiClient.get<WikiEntry>(`/wiki/${id}`),

  create: (data: WikiEntryCreate) => apiClient.post<WikiEntry>('/wiki/', data),

  update: (id: string, data: WikiEntryUpdate) =>
    apiClient.put<WikiEntry>(`/wiki/${id}`, data),

  delete: (id: string) => apiClient.delete(`/wiki/${id}`),

  search: (query: string, limit?: number) =>
    apiClient.get<WikiEntry[]>('/wiki/search/', {
      params: { q: query, limit },
    }),
}

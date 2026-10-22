import apiClient from './client'
import type {
  WikiEntry,
  WikiEntryCreate,
  WikiEntryUpdate,
  WikiDraft,
  WikiLintReport,
  WikiMergeRequest,
  WikiSearchParams,
} from '../types/wiki'

export const wikiApi = {
  list: (params?: WikiSearchParams) =>
    apiClient.get<WikiEntry[]>('/wiki/', { params }),

  draft: (selectedText: string, allowMerge = true) =>
    apiClient.post<WikiDraft>('/wiki/draft', { selected_text: selectedText, allow_merge: allowMerge }, { timeout: 90000 }),

  merge: (id: string, data: WikiMergeRequest) =>
    apiClient.post<WikiEntry>(`/wiki/${id}/merge`, data),

  lint: () => apiClient.get<WikiLintReport>('/wiki/lint'),

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

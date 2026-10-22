import apiClient from './client'
import type { PageUpdate } from '../types/space'

export const spacesApi = {
  listSpaces: () => apiClient.get('/workspace/spaces'),
  createSpace: (name: string) => apiClient.post('/workspace/spaces', { name }),
  deleteSpace: (id: string) => apiClient.delete(`/workspace/spaces/${id}`),

  listPages: (params: { view?: 'all' | 'favorites' | 'trash'; space_id?: string; q?: string }) =>
    apiClient.get('/workspace/pages', { params }),
  getPage: (id: string) => apiClient.get(`/workspace/pages/${id}`),
  createPage: (input: { title?: string; content?: string; space_id?: string | null }) =>
    apiClient.post('/workspace/pages', input),
  updatePage: (id: string, input: PageUpdate) => apiClient.put(`/workspace/pages/${id}`, input),
  trashPage: (id: string) => apiClient.delete(`/workspace/pages/${id}`),
  restorePage: (id: string) => apiClient.post(`/workspace/pages/${id}/restore`),
  deletePermanently: (id: string) => apiClient.delete(`/workspace/pages/${id}/permanent`),
  emptyTrash: () => apiClient.delete('/workspace/trash'),
}

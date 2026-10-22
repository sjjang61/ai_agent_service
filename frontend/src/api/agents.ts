import apiClient from './client'
import type { AgentConfig } from '../types/customAgent'

export const agentsApi = {
  list: () => apiClient.get('/agents'),
  catalog: () => apiClient.get('/agents/catalog'),
  get: (id: string) => apiClient.get(`/agents/${id}`),
  create: (data: { name: string; description?: string; icon?: string; config?: AgentConfig }) => apiClient.post('/agents', data),
  update: (id: string, data: { name?: string; description?: string; icon?: string; config?: AgentConfig }) =>
    apiClient.put(`/agents/${id}`, data),
  remove: (id: string) => apiClient.delete(`/agents/${id}`),
  duplicate: (id: string) => apiClient.post(`/agents/${id}/duplicate`),
  publish: (id: string, note = '') => apiClient.post(`/agents/${id}/publish`, { note }),
  versions: (id: string) => apiClient.get(`/agents/${id}/versions`),
  restoreVersion: (id: string, version: number) => apiClient.post(`/agents/${id}/versions/${version}/restore`),
  activateVersion: (id: string, version: number) => apiClient.post(`/agents/${id}/versions/${version}/activate`),
  validate: (config: AgentConfig) => apiClient.post('/agents/validate', config),
}

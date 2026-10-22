import apiClient from './client'
import type { SkillCreateInput } from '../types/skill'

export const skillsApi = {
  list: () => apiClient.get('/skills'),
  install: (url: string) => apiClient.post('/skills/install', { url }),
  create: (input: SkillCreateInput) => apiClient.post('/skills/custom', input),
  setActive: (id: string, is_active: boolean) => apiClient.post(`/skills/${id}/active`, { is_active }),
  sync: () => apiClient.post('/skills/sync'),
  remove: (id: string) => apiClient.delete(`/skills/${id}`),

  listPlugins: () => apiClient.get('/skills/plugins'),
  installPlugin: (url: string) => apiClient.post('/skills/plugins/install', { url }),
  setPluginActive: (id: string, is_active: boolean) =>
    apiClient.post(`/skills/plugins/${id}/active`, { is_active }),
  removePlugin: (id: string) => apiClient.delete(`/skills/plugins/${id}`),
}

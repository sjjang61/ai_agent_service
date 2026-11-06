import apiClient from './client'
import type { SkillCreateInput } from '../types/skill'

export const skillsApi = {
  list: () => apiClient.get('/skills'),
  install: (url: string) => apiClient.post('/skills/install', { url }),
  uploadZip: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    // axios 기본 Content-Type(application/json)을 지워 브라우저가 multipart 경계를 붙이게 한다
    return apiClient.post('/skills/upload', form, { headers: { 'Content-Type': undefined }, timeout: 120000 })
  },
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

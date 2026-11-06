import apiClient from './client'
import type { SkillCreateInput, SkillType } from '../types/skill'

export const skillsApi = {
  list: () => apiClient.get('/skills'),
  install: (url: string, skill_type?: SkillType) => apiClient.post('/skills/install', { url, skill_type }),
  setType: (id: string, skill_type: SkillType) => apiClient.post(`/skills/${id}/type`, { skill_type }),
  uploadZip: (file: File, skill_type?: SkillType) => {
    const form = new FormData()
    form.append('file', file)
    if (skill_type) form.append('skill_type', skill_type)
    // axios 기본 Content-Type(application/json)을 지워 브라우저가 multipart 경계를 붙이게 한다
    return apiClient.post('/skills/upload', form, { headers: { 'Content-Type': undefined }, timeout: 120000 })
  },
  create: (input: SkillCreateInput) => apiClient.post('/skills/custom', input),
  detail: (id: string) => apiClient.get('/skills/' + id + '/detail'),
  file: (id: string, path: string) => apiClient.get('/skills/' + id + '/file', { params: { path } }),
  translate: (id: string, path: string, refresh = false) =>
    apiClient.post('/skills/' + id + '/translate', { path, refresh }, { timeout: 300000 }),
  setActive: (id: string, is_active: boolean) => apiClient.post(`/skills/${id}/active`, { is_active }),
  sync: () => apiClient.post('/skills/sync'),
  remove: (id: string) => apiClient.delete(`/skills/${id}`),

  listPlugins: () => apiClient.get('/skills/plugins'),
  uploadPluginZip: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return apiClient.post('/skills/plugins/upload', form, { headers: { 'Content-Type': undefined }, timeout: 120000 })
  },
  installPlugin: (url: string) => apiClient.post('/skills/plugins/install', { url }),
  setPluginActive: (id: string, is_active: boolean) =>
    apiClient.post(`/skills/plugins/${id}/active`, { is_active }),
  removePlugin: (id: string) => apiClient.delete(`/skills/plugins/${id}`),
}

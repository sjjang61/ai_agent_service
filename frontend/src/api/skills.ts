import apiClient from './client'

export const skillsApi = {
  list: () => apiClient.get('/skills'),
  install: (url: string) => apiClient.post('/skills/install', { url }),
  sync: () => apiClient.post('/skills/sync'),
  remove: (id: string) => apiClient.delete(`/skills/${id}`),
}

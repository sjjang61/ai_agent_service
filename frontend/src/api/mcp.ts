import apiClient from './client'

export const mcpApi = {
  getConfigs: () => apiClient.get('/mcp/configs'),
  createConfig: (data: unknown) => apiClient.post('/mcp/configs', data),
  updateConfig: (id: string, data: unknown) => apiClient.put(`/mcp/configs/${id}`, data),
  deleteConfig: (id: string) => apiClient.delete(`/mcp/configs/${id}`),
  toggleConfig: (id: string) => apiClient.post(`/mcp/configs/${id}/toggle`),
  testConfig: (id: string) => apiClient.post(`/mcp/configs/${id}/test`),
  getTools: (id: string) => apiClient.get(`/mcp/configs/${id}/tools`),
  reloadConfig: (id: string) => apiClient.post(`/mcp/configs/${id}/reload`),
}

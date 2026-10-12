import apiClient from './client'

export const sandboxApi = {
  getStatus: () => apiClient.get('/sandbox/status'),
  startSandbox: () => apiClient.post('/sandbox/start'),
  stopSandbox: () => apiClient.post('/sandbox/stop'),
  getWorkspaceTree: () => apiClient.get<{ files: string[] }>('/sandbox/workspace-tree'),
  getFileContent: (path: string) =>
    apiClient.get<{ path: string; content: string }>(`/sandbox/files/${path}`),
}

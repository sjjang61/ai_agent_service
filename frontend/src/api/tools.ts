import apiClient from './client'
import type { ToolGroup } from '../types/tool'

export const toolsApi = {
  list: () => apiClient.get<ToolGroup[]>('/tools'),
  setEnabled: (name: string, enabled: boolean) => apiClient.put(`/tools/${name}`, { enabled }),
  setManyEnabled: (names: string[], enabled: boolean) => apiClient.put('/tools', { names, enabled }),
}

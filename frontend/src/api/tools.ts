import apiClient from './client'
import type { ToolGroup } from '../types/tool'

export const toolsApi = {
  list: () => apiClient.get<ToolGroup[]>('/tools'),
}

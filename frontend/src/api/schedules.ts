import apiClient from './client'
import type { ScheduledTask, TaskInput, TaskRun } from '../types/schedule'

export const schedulesApi = {
  list: () => apiClient.get<ScheduledTask[]>('/schedules'),
  create: (data: TaskInput) => apiClient.post<ScheduledTask>('/schedules', data),
  update: (id: string, data: Partial<TaskInput>) => apiClient.put<ScheduledTask>(`/schedules/${id}`, data),
  remove: (id: string) => apiClient.delete(`/schedules/${id}`),
  setEnabled: (id: string, enabled: boolean) => apiClient.post<ScheduledTask>(`/schedules/${id}/enabled`, { enabled }),
  runNow: (id: string) => apiClient.post<{ run_id: string; status: string }>(`/schedules/${id}/run`),
  runs: (id: string) => apiClient.get<TaskRun[]>(`/schedules/${id}/runs`),
  markTaskRead: (id: string) => apiClient.post(`/schedules/${id}/read`),
  markRunRead: (runId: string) => apiClient.post(`/schedules/runs/${runId}/read`),
  unreadCount: () => apiClient.get<{ count: number }>('/schedules/unread-count'),
}

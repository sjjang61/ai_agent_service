import apiClient from './client'

export interface ChannelStatus {
  configured: boolean
  bot_username: string | null
  enabled: boolean
  notify_schedules: boolean
  status: 'none' | 'pending' | 'connected' | 'error'
  last_error: string | null
  pair_code: string | null
  pair_expires_at: string | null
  pair_url: string | null
}

export const channelsApi = {
  telegram: () => apiClient.get<ChannelStatus>('/channels/telegram'),
  connect: (token: string) => apiClient.put<ChannelStatus>('/channels/telegram', { token }),
  newPairCode: () => apiClient.post<ChannelStatus>('/channels/telegram/pair-code'),
  setEnabled: (enabled: boolean) => apiClient.patch<ChannelStatus>('/channels/telegram', { enabled }),
  setNotify: (notify_schedules: boolean) => apiClient.patch<ChannelStatus>('/channels/telegram', { notify_schedules }),
  disconnect: () => apiClient.delete('/channels/telegram'),
}

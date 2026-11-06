import apiClient from './client'
import type {
  UsageSummary,
  DailyUsage,
  UserUsage,
  ModelUsage,
  SessionUsage,
  PricingState,
  PricingRefreshResult,
} from '../types/admin'

export const adminApi = {
  getUsageSummary: (userId?: string) =>
    apiClient.get<UsageSummary>('/admin/usage/summary', {
      params: userId ? { user_id: userId } : {},
    }),

  getDailyUsage: (days = 30, userId?: string) =>
    apiClient.get<DailyUsage[]>('/admin/usage/daily', {
      params: { days, ...(userId ? { user_id: userId } : {}) },
    }),

  getWeeklyUsage: (weeks = 12, userId?: string) =>
    apiClient.get<DailyUsage[]>('/admin/usage/weekly', {
      params: { weeks, ...(userId ? { user_id: userId } : {}) },
    }),

  getMonthlyUsage: (months = 12, userId?: string) =>
    apiClient.get<DailyUsage[]>('/admin/usage/monthly', {
      params: { months, ...(userId ? { user_id: userId } : {}) },
    }),

  getUserBreakdown: (days = 30) =>
    apiClient.get<UserUsage[]>('/admin/usage/users', { params: { days } }),

  getModelBreakdown: (days = 30, userId?: string) =>
    apiClient.get<ModelUsage[]>('/admin/usage/models', {
      params: { days, ...(userId ? { user_id: userId } : {}) },
    }),

  getPricing: () => apiClient.get<PricingState>('/admin/pricing'),

  setPricingUrl: (url: string) => apiClient.put<PricingState>('/admin/pricing/url', { url }),

  refreshPricing: () => apiClient.post<PricingRefreshResult>('/admin/pricing/refresh', {}, { timeout: 90000 }),

  getSessionUsage: (conversationId: string) =>
    apiClient.get<SessionUsage>(`/admin/usage/sessions/${conversationId}`),
}

import apiClient from './client'

export interface CalendarEvent {
  id: string
  title: string
  start_date: string // YYYY-MM-DD
  end_date: string
  start_time: string
  end_time: string
  note: string
  conversation_id: string | null
  conversation_title: string | null
  key: string | null
}

export const calendarApi = {
  events: (refresh = false) => apiClient.get<CalendarEvent[]>('/calendar/events', { params: refresh ? { refresh: true } : undefined }),
}

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
  manual: boolean
  in_memory: boolean
}

export interface EventInput {
  title: string
  start_date: string
  end_date: string
  start_time: string
  end_time: string
  note: string
  save_to_memory: boolean
}

export const calendarApi = {
  events: (refresh = false) => apiClient.get<CalendarEvent[]>('/calendar/events', { params: refresh ? { refresh: true } : undefined }),
  create: (d: EventInput) => apiClient.post<CalendarEvent>('/calendar/manual', d),
  update: (id: string, d: EventInput) => apiClient.put<CalendarEvent>(`/calendar/manual/${id}`, d),
  remove: (id: string) => apiClient.delete(`/calendar/manual/${id}`),
}

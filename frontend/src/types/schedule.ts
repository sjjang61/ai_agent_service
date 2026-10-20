export type ScheduleType = 'once' | 'interval' | 'daily' | 'weekdays' | 'weekly' | 'monthly'
export type TaskStatus = 'active' | 'paused' | 'auto_paused' | 'completed'
export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | 'skipped'

export interface TaskRun {
  id: string
  task_id: string
  status: RunStatus
  trigger: 'schedule' | 'manual'
  scheduled_for: string | null
  started_at: string | null
  finished_at: string | null
  conversation_id: string | null
  summary: string | null
  error: string | null
  unread: boolean
}

export interface ScheduledTask {
  id: string
  name: string
  prompt: string
  schedule_type: ScheduleType
  schedule_time: string | null
  weekdays: number[] | null
  day_of_month: number | null
  interval_hours: number | null
  run_at: string | null
  timezone: string
  schedule_text: string
  status: TaskStatus
  enabled: boolean
  running: boolean
  conversation_id: string | null
  new_conversation_each_run: boolean
  allow_mcp: boolean
  allow_browser: boolean
  next_run_at: string | null
  last_run_at: string | null
  last_status: string | null
  consecutive_failures: number
  unread_count: number
  last_run: TaskRun | null
  created_at: string | null
}

/** 생성/수정 폼 값 (서버의 TaskInput 과 같은 모양) */
export interface TaskInput {
  name: string
  prompt: string
  schedule_type: ScheduleType
  schedule_time: string | null
  weekdays: number[] | null
  day_of_month: number | null
  interval_hours: number | null
  run_at: string | null
  timezone: string
  new_conversation_each_run: boolean
  allow_mcp: boolean
  allow_browser: boolean
}

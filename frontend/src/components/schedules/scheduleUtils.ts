import type { RunStatus, TaskInput, TaskStatus } from '../../types/schedule'

export const WEEKDAY_LABELS = ['월', '화', '수', '목', '금', '토', '일']

export const SCHEDULE_TYPE_OPTIONS: { value: TaskInput['schedule_type']; label: string }[] = [
  { value: 'daily', label: '매일' },
  { value: 'weekdays', label: '평일 (월~금)' },
  { value: 'weekly', label: '매주' },
  { value: 'monthly', label: '매월' },
  { value: 'interval', label: '몇 시간마다' },
  { value: 'once', label: '한 번만' },
]

export function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Seoul'
  } catch {
    return 'Asia/Seoul'
  }
}

export function allTimezones(): string[] {
  try {
    const fn = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf
    const list = fn ? fn('timeZone') : []
    if (list.length) return list
  } catch {
    // 지원하지 않는 브라우저
  }
  return ['Asia/Seoul', 'Asia/Tokyo', 'UTC', 'America/New_York', 'America/Los_Angeles', 'Europe/London', 'Europe/Paris']
}

export function emptyInput(): TaskInput {
  return {
    name: '',
    prompt: '',
    schedule_type: 'daily',
    schedule_time: '09:00',
    weekdays: [0],
    day_of_month: 1,
    interval_hours: 6,
    run_at: null,
    timezone: browserTimezone(),
    new_conversation_each_run: false,
    allow_mcp: false,
    allow_browser: false,
  }
}

const dtf = (opts: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('ko-KR', opts)

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '-'
  return dtf({ month: 'numeric', day: 'numeric', weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(iso))
}

export function formatShort(iso: string | null | undefined): string {
  if (!iso) return '-'
  const d = new Date(iso)
  const now = new Date()
  const time = dtf({ hour: '2-digit', minute: '2-digit', hour12: false }).format(d)
  const dayDiff = Math.round((new Date(d.toDateString()).getTime() - new Date(now.toDateString()).getTime()) / 86400000)
  if (dayDiff === 0) return `오늘 ${time}`
  if (dayDiff === 1) return `내일 ${time}`
  if (dayDiff === -1) return `어제 ${time}`
  return `${dtf({ month: 'numeric', day: 'numeric' }).format(d)} ${time}`
}

export function relativeFromNow(iso: string | null | undefined): string {
  if (!iso) return ''
  const diff = new Date(iso).getTime() - Date.now()
  const abs = Math.abs(diff)
  const unit = abs < 3600_000 ? [Math.max(1, Math.round(abs / 60_000)), '분'] : abs < 86400_000 ? [Math.round(abs / 3600_000), '시간'] : [Math.round(abs / 86400_000), '일']
  return `${unit[0]}${unit[1]} ${diff >= 0 ? '후' : '전'}`
}

export function durationText(start: string | null, end: string | null): string {
  if (!start || !end) return ''
  const s = Math.max(0, Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000))
  return s < 60 ? `${s}초` : `${Math.floor(s / 60)}분 ${s % 60}초`
}

export const STATUS_LABEL: Record<TaskStatus, string> = {
  active: '예정',
  paused: '일시중지',
  auto_paused: '자동 중지됨',
  completed: '완료',
}

export const RUN_STATUS_LABEL: Record<RunStatus, string> = {
  queued: '대기 중',
  running: '실행 중',
  succeeded: '성공',
  failed: '실패',
  cancelled: '취소됨',
  skipped: '건너뜀',
}

/** 서버 오류 응답에서 사람이 읽을 메시지를 꺼낸다 (FastAPI 의 detail 은 문자열 또는 검증 오류 배열). */
export function errorText(e: unknown, fallback = '요청을 처리하지 못했습니다'): string {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    const d = detail[0] as { loc?: unknown[]; msg?: string }
    return `${(d.loc ?? []).slice(1).join('.')}: ${d.msg ?? ''}`.trim()
  }
  return fallback
}

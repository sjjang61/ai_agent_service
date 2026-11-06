import { DEFAULT_TIMEZONE, useSettingsStore } from '../store/settingsStore'

/** 서버는 시각을 UTC 로 주지만 'Z' 없이 보내는 경우가 있다. 그대로 new Date() 하면 브라우저 시간대로 해석되어 어긋나므로 UTC 로 고정한다. */
export function parseServerDate(iso: string): Date {
  const s = iso.includes(' ') && !iso.includes('T') ? iso.replace(' ', 'T') : iso
  const hasTime = s.includes('T')
  const hasZone = /(?:[zZ]|[+-]\d{2}:?\d{2})$/.test(s)
  return new Date(hasTime && !hasZone ? `${s}Z` : s)
}

export function currentTimezone(): string {
  const tz = useSettingsStore.getState().timezone || DEFAULT_TIMEZONE
  try {
    new Intl.DateTimeFormat('ko-KR', { timeZone: tz })
    return tz
  } catch {
    return DEFAULT_TIMEZONE
  }
}

function parts(d: Date, opts: Intl.DateTimeFormatOptions) {
  const out: Record<string, string> = {}
  for (const p of new Intl.DateTimeFormat('en-US', { timeZone: currentTimezone(), hourCycle: 'h23', ...opts }).formatToParts(d)) {
    out[p.type] = p.value
  }
  return out
}

/** 설정한 시간대 기준 날짜 키 (YYYY-MM-DD). '오늘' 구분 등에 쓴다. */
export function dayKey(d: Date): string {
  const p = parts(d, { year: 'numeric', month: '2-digit', day: '2-digit' })
  return `${p.year}-${p.month}-${p.day}`
}

/** 예: 11월 5일 오후 3:07 */
export function formatKoreanDateTime(iso: string): string {
  const d = parseServerDate(iso)
  if (isNaN(d.getTime())) return ''
  const p = parts(d, { month: 'numeric', day: 'numeric', hour: 'numeric', minute: '2-digit' })
  const h = Number(p.hour)
  return `${p.month}월 ${p.day}일 ${h < 12 ? '오전' : '오후'} ${h === 0 ? 12 : h > 12 ? h - 12 : h}:${p.minute}`
}

/** 예: 오후 2:35 */
export function formatKoreanClock(iso: string): string {
  const d = parseServerDate(iso)
  if (isNaN(d.getTime())) return ''
  const p = parts(d, { hour: 'numeric', minute: '2-digit' })
  const h = Number(p.hour)
  return `${h < 12 ? '오전' : '오후'} ${h === 0 ? 12 : h > 12 ? h - 12 : h}:${p.minute}`
}

/** 예: 11월 5일 */
export function formatMonthDay(iso: string): string {
  const d = parseServerDate(iso)
  if (isNaN(d.getTime())) return ''
  const p = parts(d, { month: 'numeric', day: 'numeric' })
  return `${p.month}월 ${p.day}일`
}

export function formatFullDateTime(iso: string | null | undefined): string {
  if (!iso) return '-'
  const d = parseServerDate(iso)
  return isNaN(d.getTime()) ? '-' : d.toLocaleString('ko-KR', { timeZone: currentTimezone() })
}

export function formatFullDate(iso: string): string {
  const d = parseServerDate(iso)
  return isNaN(d.getTime()) ? '' : d.toLocaleDateString('ko-KR', { timeZone: currentTimezone() })
}

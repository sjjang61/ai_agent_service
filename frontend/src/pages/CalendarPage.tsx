import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, ChevronDown, ChevronUp, CalendarDays, Loader2, RefreshCw } from 'lucide-react'
import SettingsPage from '../components/skills/SettingsPage'
import { headerActionCls } from '../components/skills/typography'
import { calendarApi, type CalendarEvent } from '../api/calendar'

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']
const BAR_H = 28
const BAR_GAP = 2
const DATE_ROW_H = 28
const MAX_VISIBLE = 3
// 이벤트별로 돌려 쓰는 색 (테마 토큰 기반)
const PALETTE = [
  'bg-accent-blue/20 text-accent-blue border-accent-blue',
  'bg-accent-purple/20 text-accent-purple border-accent-purple',
  'bg-accent-green/20 text-accent-green border-accent-green',
  'bg-accent-orange/20 text-accent-orange border-accent-orange',
]

const pad = (n: number) => String(n).padStart(2, '0')
const fmt = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const parse = (s: string) => new Date(`${s}T00:00:00`)

/** 해당 달을 7의 배수 칸으로 채운 날짜 배열 (앞뒤는 null) */
function buildDays(year: number, month: number): (Date | null)[] {
  const first = new Date(year, month, 1)
  const cells: (Date | null)[] = Array(first.getDay()).fill(null)
  for (let d = 1; d <= new Date(year, month + 1, 0).getDate(); d++) cells.push(new Date(year, month, d))
  while (cells.length % 7) cells.push(null)
  return cells
}

/** 겹치는 이벤트가 다른 줄(lane)에 놓이도록 배정 */
function assignLanes(events: CalendarEvent[]) {
  const sorted = [...events].sort((a, b) => a.start_date.localeCompare(b.start_date) || b.end_date.localeCompare(a.end_date))
  const laneEnds: string[] = []
  const lane = new Map<string, number>()
  for (const ev of sorted) {
    let i = laneEnds.findIndex((end) => ev.start_date > end)
    if (i < 0) { i = laneEnds.length; laneEnds.push(ev.end_date) } else laneEnds[i] = ev.end_date
    lane.set(ev.id, i)
  }
  return { sorted, lane }
}

function colorOf(ev: CalendarEvent, all: CalendarEvent[]) {
  return PALETTE[Math.max(0, all.findIndex((e) => e.id === ev.id)) % PALETTE.length]
}

function timeLabel(ev: CalendarEvent) {
  if (!ev.start_time) return ''
  return ev.end_time ? `${ev.start_time}~${ev.end_time}` : ev.start_time
}

function WeekRow({ week, events, lanes, all, today, month, onOpen }: {
  week: (Date | null)[]; events: CalendarEvent[]; lanes: Map<string, number>; all: CalendarEvent[]
  today: string; month: number; onOpen: (ev: CalendarEvent) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const first = week.find((d) => d)!
  const last = [...week].reverse().find((d) => d)!
  const ws = fmt(first), we = fmt(last)
  const weekEvents = events.filter((e) => e.start_date <= we && e.end_date >= ws)
    .sort((a, b) => (lanes.get(a.id) ?? 0) - (lanes.get(b.id) ?? 0))
  const visible = expanded ? weekEvents : weekEvents.slice(0, MAX_VISIBLE)
  const overlayH = visible.length * (BAR_H + BAR_GAP)
  const col = 100 / 7

  return (
    <div className="min-w-0">
      <div className="relative grid grid-cols-7">
        {week.map((d, i) => {
          const ds = d ? fmt(d) : ''
          const isToday = ds === today
          return (
            <div
              key={i}
              style={{ minHeight: Math.max(96, DATE_ROW_H + overlayH + 8) }}
              className={`min-w-0 border-r border-b border-border p-1.5 ${!d || d.getMonth() !== month ? 'bg-surface-tertiary/40' : 'bg-surface-secondary'} ${isToday ? '!bg-accent-primary/10' : ''}`}
            >
              {d && (
                <span
                  aria-current={isToday ? 'date' : undefined}
                  className={`inline-flex min-w-5 items-center justify-center text-xs font-medium
                    ${isToday ? 'w-[22px] h-[22px] rounded-full bg-accent-primary text-white font-bold' : i === 0 ? 'text-accent-red' : i === 6 ? 'text-accent-blue' : 'text-content-secondary'}`}
                >
                  {d.getDate()}
                </span>
              )}
            </div>
          )
        })}
        {visible.map((ev, row) => {
          const cs = ev.start_date < ws ? ws : ev.start_date
          const ce = ev.end_date > we ? we : ev.end_date
          const sd = parse(cs).getDay(), ed = parse(ce).getDay()
          const isStart = ev.start_date >= ws, isEnd = ev.end_date <= we
          const t = timeLabel(ev)
          return (
            <button
              key={`${ev.id}-${ws}`}
              onClick={() => onOpen(ev)}
              title={`${ev.title} (${ev.start_date}${ev.end_date !== ev.start_date ? ` ~ ${ev.end_date}` : ''}${t ? ` ${t}` : ''})${ev.note ? `\n${ev.note}` : ''}`}
              style={{ left: `calc(${sd * col}% + 3px)`, width: `calc(${(ed - sd + 1) * col}% - 6px)`, top: DATE_ROW_H + row * (BAR_H + BAR_GAP), height: BAR_H }}
              className={`absolute z-[2] flex items-center gap-1 px-2 text-xs text-left overflow-hidden border-l-[3px] cursor-pointer hover:brightness-110
                ${colorOf(ev, all)} ${isStart ? 'rounded-l' : 'border-l-transparent'} ${isEnd ? 'rounded-r' : ''}`}
            >
              <span className="truncate flex-1">{ev.title}</span>
              {t && isStart && <span className="opacity-70 flex-shrink-0">{ev.start_time}</span>}
            </button>
          )
        })}
      </div>
      {weekEvents.length > MAX_VISIBLE && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="w-full flex items-center gap-1 px-2 py-1 text-xs text-content-muted hover:text-content-primary border-b border-border"
        >
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          {expanded ? '접기' : `더 보기 (+${weekEvents.length - MAX_VISIBLE})`}
        </button>
      )}
    </div>
  )
}

export default function CalendarPage() {
  const navigate = useNavigate()
  const [month, setMonth] = useState(() => { const n = new Date(); return new Date(n.getFullYear(), n.getMonth(), 1) })
  const today = fmt(new Date())

  const { data: events = [], isLoading, isError, error, isFetching, refetch } = useQuery({
    queryKey: ['calendar-events'],
    queryFn: async () => (await calendarApi.events()).data,
    staleTime: 60_000,
    retry: false,
  })

  const days = useMemo(() => buildDays(month.getFullYear(), month.getMonth()), [month])
  const weeks = useMemo(() => Array.from({ length: days.length / 7 }, (_, i) => days.slice(i * 7, i * 7 + 7)), [days])
  const { lane } = useMemo(() => assignLanes(events), [events])
  const monthStart = fmt(month)
  const monthEnd = fmt(new Date(month.getFullYear(), month.getMonth() + 1, 0))
  const inMonth = events.filter((e) => e.start_date <= monthEnd && e.end_date >= monthStart)
    .sort((a, b) => a.start_date.localeCompare(b.start_date))

  const shift = (n: number) => setMonth((m) => new Date(m.getFullYear(), m.getMonth() + n, 1))
  const goToday = () => { const n = new Date(); setMonth(new Date(n.getFullYear(), n.getMonth(), 1)) }
  const open = (ev: CalendarEvent) => ev.conversation_id && navigate(`/chat/${ev.conversation_id}`)
  const errMsg = (error as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail

  return (
    <SettingsPage
      active="calendar"
      title="캘린더"
      subtitle="단기 메모리에 기억된 일정을 월별 캘린더로 확인합니다."
      actions={
        <button onClick={async () => { await calendarApi.events(true).then(() => refetch()).catch(() => refetch()) }} disabled={isFetching} className={headerActionCls}>
          {isFetching ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} 다시 추출
        </button>
      }
    >
      <div className="grid min-w-0 grid-cols-1 items-start gap-4 xl:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="min-w-0 border border-border rounded-xl overflow-hidden bg-surface-secondary">
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-b border-border">
            <h2 className="text-[16px] font-semibold text-content-primary">{month.getFullYear()}년 {month.getMonth() + 1}월</h2>
            <div className="flex items-center gap-1">
              <button onClick={goToday} className="px-3 py-1.5 rounded-lg text-xs bg-surface-tertiary text-content-secondary hover:text-content-primary">오늘</button>
              <button onClick={() => shift(-1)} aria-label="이전 달" className="p-1.5 rounded-lg text-content-muted hover:text-content-primary hover:bg-surface-hover"><ChevronLeft size={16} /></button>
              <button onClick={() => shift(1)} aria-label="다음 달" className="p-1.5 rounded-lg text-content-muted hover:text-content-primary hover:bg-surface-hover"><ChevronRight size={16} /></button>
            </div>
          </div>
          <div className="grid grid-cols-7 border-b border-border bg-surface-tertiary/50">
            {WEEKDAYS.map((w, i) => (
              <div key={w} className={`px-2 py-2 text-center text-xs font-semibold ${i === 0 ? 'text-accent-red' : i === 6 ? 'text-accent-blue' : 'text-content-muted'}`}>{w}</div>
            ))}
          </div>
          {isLoading ? (
            <div className="flex items-center justify-center gap-2 py-16 text-sm text-content-muted"><Loader2 size={14} className="animate-spin" /> 일정을 불러오는 중...</div>
          ) : isError ? (
            <div className="py-12 text-center text-sm text-accent-red px-4">
              {errMsg || '일정을 불러오지 못했습니다.'}
              <div><button onClick={() => refetch()} className="mt-2 text-xs underline text-content-secondary">다시 시도</button></div>
            </div>
          ) : (
            weeks.map((w, i) => (
              <WeekRow key={i} week={w} events={events} lanes={lane} all={events} today={today} month={month.getMonth()} onOpen={open} />
            ))
          )}
        </div>

        <div className="min-w-0 border border-border rounded-xl bg-surface-secondary">
          <div className="px-4 py-3 border-b border-border text-sm font-semibold text-content-primary">{month.getMonth() + 1}월 일정</div>
          <div className="p-3 flex flex-col gap-2">
            {!isLoading && !isError && inMonth.length === 0 && (
              <div className="text-center text-content-muted py-8">
                <CalendarDays size={28} className="mx-auto mb-2 opacity-50" />
                <p className="text-sm">이 달에 기억된 일정이 없습니다.</p>
              </div>
            )}
            {inMonth.map((ev) => (
              <button
                key={ev.id}
                onClick={() => open(ev)}
                disabled={!ev.conversation_id}
                className="text-left rounded-lg border border-border p-3 hover:border-border-light transition-colors min-w-0"
              >
                <div className="text-[13px] font-medium text-content-primary break-words">{ev.title}</div>
                <div className="mt-1 text-xs text-content-tertiary">
                  {ev.start_date.slice(5).replace('-', '/')}{ev.end_date !== ev.start_date && ` ~ ${ev.end_date.slice(5).replace('-', '/')}`}
                  {timeLabel(ev) && ` · ${timeLabel(ev)}`}
                </div>
                {ev.note && <p className="mt-1 text-xs text-content-secondary break-words">{ev.note}</p>}
                {ev.conversation_title && <p className="mt-1 text-[11px] text-content-tertiary truncate">대화: {ev.conversation_title}</p>}
              </button>
            ))}
          </div>
        </div>
      </div>
    </SettingsPage>
  )
}

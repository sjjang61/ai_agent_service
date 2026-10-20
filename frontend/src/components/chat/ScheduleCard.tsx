import { CalendarClock } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import type { AgentStepData } from '../../types/chat'
import { formatShort } from '../schedules/scheduleUtils'

type Action = 'create' | 'update' | 'pause' | 'resume' | 'delete'

interface BriefTask {
  id: string
  name: string
  schedule_text?: string
  status?: string
  next_run_at?: string | null
}

export interface ScheduleResult {
  action: Action
  tasks: BriefTask[]
}

const TITLES: Record<Action, string> = {
  create: '예약을 만들었습니다',
  update: '예약을 수정했습니다',
  pause: '예약을 일시중지했습니다',
  resume: '예약을 재개했습니다',
  delete: '예약을 삭제했습니다',
}

/** manage_schedule 의 성공 결과(조회 제외)를 꺼낸다. 오류 문장("Error: ...")은 무시한다. */
export function extractScheduleResults(steps: AgentStepData[] | undefined): ScheduleResult[] {
  const out: ScheduleResult[] = []
  for (const s of steps ?? []) {
    if (s.type !== 'tool_result' || s.tool !== 'manage_schedule' || typeof s.output !== 'string') continue
    try {
      const p = JSON.parse(s.output)
      if (!p?.ok || !(p.action in TITLES)) continue
      const tasks: BriefTask[] = Array.isArray(p.tasks) ? p.tasks : p.task ? [p.task] : []
      if (tasks.length) out.push({ action: p.action as Action, tasks })
    } catch {
      // JSON 이 아니면 오류 문장
    }
  }
  return out
}

export default function ScheduleCard({ result }: { result: ScheduleResult }) {
  const navigate = useNavigate()
  const { action, tasks } = result
  const shown = tasks.slice(0, 5)
  return (
    <div className="mb-3 rounded-[var(--radius-lg)] border border-border bg-surface-secondary p-3.5">
      <div className="flex items-center gap-2 mb-2">
        <CalendarClock size={16} className="text-accent-primary" />
        <span className="text-[13px] font-semibold text-content-primary">
          {TITLES[action]}
          {tasks.length > 1 && <span className="ml-1.5 font-normal text-content-tertiary">({tasks.length}개)</span>}
        </span>
      </div>
      <ul className="space-y-1.5">
        {shown.map((t) => (
          <li key={t.id} className="text-[13px]">
            <span className="text-content-primary">{t.name}</span>
            {action !== 'delete' && t.schedule_text && <span className="text-content-tertiary"> · {t.schedule_text}</span>}
            {action !== 'delete' && t.next_run_at && t.status === 'active' && (
              <span className="block text-xs text-content-tertiary">다음 실행: {formatShort(t.next_run_at)}</span>
            )}
            {action !== 'delete' && t.status === 'paused' && <span className="block text-xs text-content-tertiary">일시중지됨</span>}
          </li>
        ))}
        {tasks.length > shown.length && <li className="text-xs text-content-tertiary">외 {tasks.length - shown.length}개</li>}
      </ul>
      {action !== 'delete' && (
        <button onClick={() => navigate('/schedules')} className="mt-2.5 text-xs text-accent-primary hover:underline">
          예약 화면에서 보기
        </button>
      )}
    </div>
  )
}

import { CheckCircle2, CircleSlash, Clock, Loader2, MessageSquare, Pause, Pencil, Play, SkipForward, Trash2, XCircle, Zap } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import type { RunStatus, ScheduledTask, TaskRun } from '../../types/schedule'
import { RUN_STATUS_LABEL, STATUS_LABEL, durationText, formatDateTime, formatShort, relativeFromNow } from './scheduleUtils'

interface Props {
  task: ScheduledTask
  runs: TaskRun[]
  busy: boolean
  onRunNow: () => void
  onToggle: () => void
  onEdit: () => void
  onDelete: () => void
  onOpenResult: (run: TaskRun) => void
  onMarkAllRead: () => void
}

const STATUS_BADGE: Record<ScheduledTask['status'], string> = {
  active: 'bg-accent-green/15 text-accent-green',
  paused: 'bg-surface-hover text-content-secondary',
  auto_paused: 'bg-accent-red/15 text-accent-red',
  completed: 'bg-surface-hover text-content-secondary',
}

function RunIcon({ status }: { status: RunStatus }) {
  const p = { size: 15, className: 'flex-shrink-0' }
  if (status === 'succeeded') return <CheckCircle2 {...p} className="flex-shrink-0 text-accent-green" />
  if (status === 'failed') return <XCircle {...p} className="flex-shrink-0 text-accent-red" />
  if (status === 'running' || status === 'queued') return <Loader2 {...p} className="flex-shrink-0 animate-spin text-accent-primary" />
  if (status === 'skipped') return <SkipForward {...p} className="flex-shrink-0 text-content-tertiary" />
  return <CircleSlash {...p} className="flex-shrink-0 text-content-tertiary" />
}

function Info({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs text-content-tertiary mb-0.5">{label}</div>
      <div className="text-[13px] text-content-primary">{children}</div>
    </div>
  )
}

export default function TaskDetail({ task, runs, busy, onRunNow, onToggle, onEdit, onDelete, onOpenResult, onMarkAllRead }: Props) {
  const navigate = useNavigate()
  const canResume = task.status === 'paused' || task.status === 'auto_paused'
  const btn =
    'flex items-center gap-1.5 px-3 py-2 rounded-[var(--radius-md)] text-[13px] border border-border text-content-secondary hover:bg-surface-hover hover:text-content-primary disabled:opacity-40 transition-colors'

  return (
    <div className="max-w-[760px] mx-auto p-6 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5">
            <h2 className="text-[18px] font-semibold text-content-primary truncate">{task.name}</h2>
            <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium flex-shrink-0 ${STATUS_BADGE[task.status]}`}>{STATUS_LABEL[task.status]}</span>
          </div>
          <p className="text-[13px] text-content-secondary mt-1">{task.schedule_text}</p>
        </div>
        <div className="flex gap-1.5 flex-shrink-0">
          <button onClick={onRunNow} disabled={busy || task.running} className={btn} title="일정과 별개로 지금 한 번 실행합니다">
            {task.running ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
            지금 실행
          </button>
          {task.status !== 'completed' && (
            <button onClick={onToggle} disabled={busy} className={btn}>
              {canResume ? <Play size={14} /> : <Pause size={14} />}
              {canResume ? '재개' : '일시중지'}
            </button>
          )}
          <button onClick={onEdit} disabled={busy} className={btn} title="편집"><Pencil size={14} /></button>
          <button onClick={onDelete} disabled={busy} className={`${btn} hover:!text-accent-red`} title="삭제"><Trash2 size={14} /></button>
        </div>
      </div>

      {task.status === 'auto_paused' && (
        <div className="rounded-[var(--radius-md)] border border-accent-red/40 bg-accent-red/10 px-4 py-3 text-[13px] text-accent-red">
          연속 {task.consecutive_failures}회 실패해서 자동으로 일시중지되었습니다. 원인을 확인하고 재개하세요.
        </div>
      )}

      <div className="grid grid-cols-2 gap-x-6 gap-y-4 rounded-[var(--radius-lg)] border border-border bg-surface-secondary p-5">
        <Info label="다음 실행">
          {task.next_run_at ? (
            <>
              {formatDateTime(task.next_run_at)} <span className="text-content-tertiary">· {relativeFromNow(task.next_run_at)}</span>
            </>
          ) : (
            <span className="text-content-tertiary">{task.status === 'completed' ? '완료됨' : '예정 없음'}</span>
          )}
        </Info>
        <Info label="마지막 실행">{task.last_run_at ? <>{formatShort(task.last_run_at)} · {task.last_status ?? ''}</> : <span className="text-content-tertiary">아직 없음</span>}</Info>
        <Info label="시간대">{task.timezone}</Info>
        <Info label="옵션">
          <div className="flex flex-wrap gap-1.5">
            {[task.agent_name && `에이전트: ${task.agent_name}`, task.new_conversation_each_run && '실행마다 새 대화', task.allow_mcp && 'MCP 허용', task.allow_browser && '브라우저 허용'].filter(Boolean).map((x) => (
              <span key={String(x)} className="px-2 py-0.5 rounded-full bg-surface-hover text-[11px] text-content-secondary">{x}</span>
            ))}
            {!task.agent_name && !task.new_conversation_each_run && !task.allow_mcp && !task.allow_browser && <span className="text-content-tertiary">기본</span>}
          </div>
        </Info>
        <div className="col-span-2">
          <div className="text-xs text-content-tertiary mb-1">할 일</div>
          <p className="text-[13px] text-content-primary whitespace-pre-wrap leading-relaxed">{task.prompt}</p>
        </div>
        {task.conversation_id && !task.new_conversation_each_run && (
          <div className="col-span-2">
            <button onClick={() => navigate(`/chat/${task.conversation_id}`)} className="inline-flex items-center gap-1.5 text-[13px] text-accent-primary hover:underline">
              <MessageSquare size={14} /> 결과 대화 열기
            </button>
          </div>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-[14px] font-semibold text-content-primary">실행 이력</h3>
          {task.unread_count > 0 && (
            <button onClick={onMarkAllRead} className="text-xs text-content-tertiary hover:text-content-primary transition-colors">모두 읽음으로 표시</button>
          )}
        </div>
        {runs.length === 0 ? (
          <div className="flex items-center gap-2 text-[13px] text-content-muted py-6 justify-center">
            <Clock size={15} /> 아직 실행된 적이 없습니다. '지금 실행'으로 먼저 시험해 볼 수 있습니다.
          </div>
        ) : (
          <ul className="divide-y divide-border rounded-[var(--radius-lg)] border border-border overflow-hidden">
            {runs.map((r) => (
              <li key={r.id} className="flex items-start gap-3 px-4 py-3 bg-surface-primary">
                <div className="pt-0.5"><RunIcon status={r.status} /></div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 text-[13px]">
                    <span className="text-content-primary">{formatDateTime(r.started_at ?? r.scheduled_for)}</span>
                    <span className="text-content-tertiary">{RUN_STATUS_LABEL[r.status]}</span>
                    {r.trigger === 'manual' && <span className="px-1.5 py-0.5 rounded bg-surface-hover text-[10px] text-content-secondary">수동</span>}
                    {r.unread && <span className="w-1.5 h-1.5 rounded-full bg-accent-primary" title="읽지 않음" />}
                    <span className="text-xs text-content-muted ml-auto">{durationText(r.started_at, r.finished_at)}</span>
                  </div>
                  {(r.summary || r.error) && (
                    <p className={`text-xs mt-1 line-clamp-2 ${r.status === 'failed' || r.status === 'skipped' ? 'text-accent-red' : 'text-content-secondary'}`}>
                      {r.status === 'succeeded' ? r.summary : r.error ?? r.summary}
                    </p>
                  )}
                </div>
                {r.conversation_id && (r.status === 'succeeded' || r.status === 'failed' || r.status === 'cancelled') && (
                  <button onClick={() => onOpenResult(r)} className="text-xs text-accent-primary hover:underline flex-shrink-0 pt-0.5">결과 보기</button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

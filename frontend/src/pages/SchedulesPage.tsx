import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Plus, Search } from 'lucide-react'
import IconBar from '../components/layout/IconBar'
import TaskForm from '../components/schedules/TaskForm'
import TaskDetail from '../components/schedules/TaskDetail'
import { TASK_TEMPLATES } from '../components/schedules/templates'
import { emptyInput, errorText, formatShort, STATUS_LABEL } from '../components/schedules/scheduleUtils'
import { schedulesApi } from '../api/schedules'
import type { ScheduledTask, TaskInput, TaskRun } from '../types/schedule'

type View = { kind: 'empty' } | { kind: 'create'; preset: TaskInput } | { kind: 'detail'; id: string } | { kind: 'edit'; id: string }

function toInput(t: ScheduledTask): TaskInput {
  return {
    name: t.name, prompt: t.prompt, schedule_type: t.schedule_type, schedule_time: t.schedule_time, weekdays: t.weekdays ?? [0],
    day_of_month: t.day_of_month ?? 1, interval_hours: t.interval_hours ?? 6, run_at: t.run_at, timezone: t.timezone,
    new_conversation_each_run: t.new_conversation_each_run, allow_mcp: t.allow_mcp, allow_browser: t.allow_browser, agent_id: t.agent_id,
  }
}

function TaskRow({ task, active, onClick }: { task: ScheduledTask; active: boolean; onClick: () => void }) {
  const sub =
    task.status === 'active'
      ? formatShort(task.next_run_at)
      : task.status === 'completed'
      ? `완료 · ${formatShort(task.last_run_at)}`
      : STATUS_LABEL[task.status]
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2.5 rounded-[var(--radius-md)] transition-colors ${active ? 'bg-surface-active' : 'hover:bg-surface-hover'}`}
    >
      <div className="flex items-center gap-2">
        <span className="text-[13px] text-content-primary truncate flex-1">{task.name}</span>
        {task.running && <Loader2 size={12} className="animate-spin text-accent-primary flex-shrink-0" />}
        {task.unread_count > 0 && <span className="w-2 h-2 rounded-full bg-accent-primary flex-shrink-0" title="읽지 않은 결과" />}
      </div>
      <div className={`text-xs mt-0.5 ${task.status === 'auto_paused' ? 'text-accent-red' : 'text-content-tertiary'}`}>{sub}</div>
    </button>
  )
}

export default function SchedulesPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [view, setView] = useState<View>({ kind: 'empty' })
  const [search, setSearch] = useState('')
  const [showSearch, setShowSearch] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const { data: tasks = [], isLoading } = useQuery({
    queryKey: ['schedules'],
    queryFn: async () => (await schedulesApi.list()).data,
    // 실행 중인 작업이 있으면 결과가 나올 때까지 자주 갱신한다
    refetchInterval: (q) => ((q.state.data as ScheduledTask[] | undefined)?.some((t) => t.running) ? 3000 : 15000),
  })

  const selected = view.kind === 'detail' || view.kind === 'edit' ? tasks.find((t) => t.id === view.id) : undefined
  const { data: runs = [] } = useQuery({
    queryKey: ['schedule-runs', selected?.id],
    queryFn: async () => (await schedulesApi.runs(selected!.id)).data,
    enabled: !!selected,
    refetchInterval: selected?.running ? 3000 : 15000,
  })

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['schedules'] })
    qc.invalidateQueries({ queryKey: ['schedule-runs'] })
    qc.invalidateQueries({ queryKey: ['schedules-unread'] })
  }
  const run = useMutation({
    mutationFn: async (fn: () => Promise<unknown>) => fn(),
    onSuccess: () => { setActionError(null); refresh() },
    onError: (e) => setActionError(errorText(e)),
  })

  const q = search.trim().toLowerCase()
  const visible = useMemo(() => tasks.filter((t) => !q || t.name.toLowerCase().includes(q) || t.prompt.toLowerCase().includes(q)), [tasks, q])
  const upcoming = visible.filter((t) => t.status === 'active').sort((a, b) => (a.next_run_at ?? '').localeCompare(b.next_run_at ?? ''))
  const others = visible.filter((t) => t.status !== 'active')

  const openResult = async (r: TaskRun) => {
    if (r.unread) await schedulesApi.markRunRead(r.id).catch(() => undefined)
    qc.invalidateQueries({ queryKey: ['schedules-unread'] })
    if (r.conversation_id) navigate(`/chat/${r.conversation_id}`)
  }

  return (
    <div className="flex h-screen bg-surface-primary overflow-hidden">
      <IconBar />

      {/* 목록 패널 */}
      <aside className="w-[300px] flex-shrink-0 bg-surface-secondary border-r border-border flex flex-col">
        <div className="h-[52px] flex items-center justify-between px-4 flex-shrink-0">
          <h1 className="text-[15px] font-semibold text-content-primary">예약</h1>
          <button onClick={() => setShowSearch((s) => !s)} title="검색" className="text-content-tertiary hover:text-content-primary transition-colors">
            <Search size={16} />
          </button>
        </div>
        {showSearch && (
          <div className="px-3 pb-2">
            <input
              autoFocus
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="작업 검색"
              className="w-full px-3 py-2 bg-surface-primary border border-border rounded-[var(--radius-md)] text-[13px] text-content-primary placeholder:text-content-muted focus:outline-none focus:border-accent-primary"
            />
          </div>
        )}
        <div className="px-3 pb-2">
          <button
            onClick={() => setView({ kind: 'create', preset: emptyInput() })}
            className="w-full flex items-center gap-2 px-3 py-2.5 rounded-[var(--radius-md)] bg-surface-hover hover:bg-surface-active text-[13px] text-content-primary transition-colors"
          >
            <Plus size={15} /> 새 작업
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 pb-4">
          {isLoading ? (
            <p className="text-xs text-content-muted px-3 py-4">불러오는 중...</p>
          ) : (
            <>
              <div className="px-3 pt-2 pb-1 text-xs text-content-tertiary">예정</div>
              {upcoming.length === 0 ? (
                <p className="text-xs text-content-muted px-3 py-2">예약된 작업이 없습니다</p>
              ) : (
                upcoming.map((t) => <TaskRow key={t.id} task={t} active={selected?.id === t.id} onClick={() => setView({ kind: 'detail', id: t.id })} />)
              )}
              {others.length > 0 && (
                <>
                  <div className="px-3 pt-4 pb-1 text-xs text-content-tertiary">일시중지 · 완료</div>
                  {others.map((t) => <TaskRow key={t.id} task={t} active={selected?.id === t.id} onClick={() => setView({ kind: 'detail', id: t.id })} />)}
                </>
              )}
            </>
          )}
        </div>
      </aside>

      {/* 메인 */}
      <main className="flex-1 min-w-0 overflow-y-auto">
        {actionError && (
          <div className="mx-6 mt-4 rounded-[var(--radius-md)] border border-accent-red/40 bg-accent-red/10 px-4 py-2.5 text-[13px] text-accent-red">
            {actionError}
            <button onClick={() => setActionError(null)} className="ml-3 underline opacity-70">닫기</button>
          </div>
        )}

        {view.kind === 'create' && (
          <TaskForm
            key={JSON.stringify(view.preset)}
            mode="create"
            initial={view.preset}
            onCancel={() => setView({ kind: 'empty' })}
            onSubmit={async (input) => {
              const res = await schedulesApi.create(input)
              refresh()
              setView({ kind: 'detail', id: res.data.id })
            }}
          />
        )}

        {view.kind === 'edit' && selected && (
          <TaskForm
            key={selected.id}
            mode="edit"
            initial={toInput(selected)}
            onCancel={() => setView({ kind: 'detail', id: selected.id })}
            onSubmit={async (input) => {
              await schedulesApi.update(selected.id, input)
              refresh()
              setView({ kind: 'detail', id: selected.id })
            }}
          />
        )}

        {view.kind === 'detail' && selected && (
          <TaskDetail
            task={selected}
            runs={runs}
            busy={run.isPending}
            onRunNow={() => run.mutate(() => schedulesApi.runNow(selected.id))}
            onToggle={() => run.mutate(() => schedulesApi.setEnabled(selected.id, selected.status !== 'active'))}
            onEdit={() => setView({ kind: 'edit', id: selected.id })}
            onDelete={() => {
              if (!confirm(`'${selected.name}' 작업을 삭제할까요?\n실행 이력은 삭제되고, 결과 대화는 남습니다.`)) return
              run.mutate(async () => {
                await schedulesApi.remove(selected.id)
                setView({ kind: 'empty' })
              })
            }}
            onOpenResult={openResult}
            onMarkAllRead={() => run.mutate(() => schedulesApi.markTaskRead(selected.id))}
          />
        )}

        {(view.kind === 'empty' || ((view.kind === 'detail' || view.kind === 'edit') && !selected && !isLoading)) && (
          <div className="min-h-full flex flex-col items-center justify-center px-8 py-12">
            <div className="text-5xl mb-4">🕐</div>
            <h2 className="text-[20px] font-semibold text-content-primary">작업 예약하기</h2>
            <p className="text-[13px] text-content-tertiary mt-1.5 mb-8">지속적으로 해야 하는 작업을 에이전트가 대신 처리할 수 있습니다.</p>
            <div className="grid grid-cols-2 gap-3 w-full max-w-[760px]">
              {TASK_TEMPLATES.map((tpl) => (
                <button
                  key={tpl.title}
                  onClick={() => setView({ kind: 'create', preset: { ...emptyInput(), ...tpl.preset } })}
                  className="flex items-start gap-3 text-left p-4 rounded-[var(--radius-lg)] border border-dashed border-border hover:bg-surface-hover hover:border-solid transition-colors"
                >
                  <span className="text-xl leading-none mt-0.5">{tpl.emoji}</span>
                  <span className="min-w-0">
                    <span className="block text-[14px] font-medium text-content-primary">{tpl.title}</span>
                    <span className="block text-xs text-content-tertiary mt-1 leading-relaxed">{tpl.description}</span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, CheckCircle2, ChevronRight, Circle, Loader2 } from 'lucide-react'
import type { AgentStep, SelectedStepDetail } from '../../types/agent'
import { useAgentStore } from '../../store/agentStore'
import { buildPlanBuckets, buildTaskItems, currentTask, groupUnit, type TaskItem } from './taskItems'
import { extractLatestTodos, type TodoItem } from './TodoCard'

interface Props {
  steps: AgentStep[]
  running: boolean
}

/** 행을 눌렀을 때 상세 패널에 넘길 단계: 결과가 있으면 결과, 없으면 호출 */
function detailOf(item: TaskItem): SelectedStepDetail | null {
  const s = item.result ?? item.call
  if (!s) return null
  return { id: s.id, type: s.type, tool: s.tool, content: s.content, input: item.call?.input ?? s.input, output: s.output }
}

/** 합쳐진 작업의 개별 항목(파일 하나 등): 읽었는지 한눈에 보이고, 누르면 상세를 연다 */
function ChildRow({ item, showLabel = false }: { item: TaskItem; showLabel?: boolean }) {
  const { selectedStep, setSelectedStep } = useAgentStore()
  const detail = detailOf(item)
  const selected = !!selectedStep && [item.call?.id, item.result?.id].includes(selectedStep.id)
  return (
    <li>
      <button
        onClick={() => detail && setSelectedStep(selected ? null : detail)}
        className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-[var(--radius-md)] text-left border-none cursor-pointer text-xs ${selected ? 'bg-surface-active' : 'bg-transparent hover:bg-surface-hover'}`}
      >
        {item.status === 'running' ? (
          <Loader2 size={12} className="animate-spin text-accent-primary flex-shrink-0" />
        ) : item.status === 'failed' ? (
          <AlertCircle size={12} className="text-accent-red flex-shrink-0" />
        ) : (
          <CheckCircle2 size={12} className="text-accent-green flex-shrink-0" />
        )}
        {showLabel ? (
          <span className="min-w-0 flex-1" title={item.summary}>
            <span className={`block truncate ${item.status === 'failed' ? 'text-accent-red' : item.status === 'done' ? 'text-content-tertiary line-through' : 'text-content-primary'}`}>{item.label}</span>
            {item.summary && <span className="block truncate text-content-muted">{item.summary}</span>}
          </span>
        ) : (
          <span className={`truncate ${item.status === 'failed' ? 'text-accent-red' : 'text-content-secondary'}`} title={item.summary}>{item.summary || item.label}</span>
        )}
      </button>
    </li>
  )
}

function GroupRow({ item }: { item: TaskItem }) {
  const { selectedStep, setSelectedStep } = useAgentStore()
  const kids = item.children ?? []
  const delegate = item.childKind === 'delegate'
  const ownDetail = delegate ? detailOf(item) : null
  const running = item.status === 'running'
  const failed = item.status === 'failed'
  const done = item.status === 'done'
  const [toggled, setToggled] = useState<boolean | null>(null)
  const open = toggled ?? running // 진행 중에는 펼쳐 지금 어떤 파일을 읽는지 보여 주고, 끝나면 접는다
  const finished = kids.filter((k) => k.status !== 'running').length
  const box = running ? 'border-accent-primary bg-accent-primary/10' : failed ? 'border-accent-red/40 bg-surface-secondary' : 'border-border bg-surface-secondary'
  return (
    <div className={`rounded-[var(--radius-lg)] border ${box}`} aria-current={running ? 'step' : undefined}>
      <button onClick={() => setToggled(!open)} aria-expanded={open} className="w-full flex items-center gap-2.5 px-3 py-2.5 text-left border-none bg-transparent cursor-pointer">
        <span className="flex-shrink-0" aria-hidden>
          {running ? <Loader2 size={15} className="animate-spin text-accent-primary" /> : failed ? <AlertCircle size={15} className="text-accent-red" /> : <CheckCircle2 size={15} className="text-accent-green" />}
        </span>
        <span className="min-w-0 flex-1">
          <span className={`block text-[13px] font-medium truncate ${done ? 'line-through text-content-tertiary' : failed ? 'text-accent-red' : 'text-content-primary'}`}>
            {item.label}{' '}
            <span className="font-normal text-content-tertiary no-underline">
              · {delegate ? '하위 작업' : groupUnit(item.tool)} {kids.length}개{running ? ` 중 ${finished}개 완료` : ''}
            </span>
          </span>
          {item.summary && <span className={`block text-xs truncate ${done ? 'line-through text-content-muted' : 'text-content-secondary'}`}>{item.summary}</span>}
        </span>
        {running && <span className="flex-shrink-0 text-[11px] px-2 py-0.5 rounded-full bg-accent-primary/20 text-accent-primary">진행 중</span>}
        {failed && <span className="flex-shrink-0 text-[11px] px-2 py-0.5 rounded-full bg-accent-red/15 text-accent-red">일부 실패</span>}
        <ChevronRight size={13} className={`flex-shrink-0 text-content-muted transition-transform ${open ? 'rotate-90' : ''}`} aria-hidden />
      </button>
      {open && (
        <ul className="px-2 pb-2 space-y-0.5 border-t border-border/60 pt-1.5 mx-1">
          {ownDetail && (
            <li>
              <button
                onClick={() => setSelectedStep(selectedStep?.id === ownDetail.id ? null : ownDetail)}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded-[var(--radius-md)] text-left border-none cursor-pointer text-xs bg-transparent hover:bg-surface-hover text-content-tertiary"
              >
                <ChevronRight size={12} className="flex-shrink-0" /> 위임 내용·결과 보기
              </button>
            </li>
          )}
          {kids.map((k) =>
            k.children ? (
              <li key={k.key}><GroupRow item={k} /></li>
            ) : (
              <ChildRow key={k.key} item={k} showLabel={delegate} />
            )
          )}
        </ul>
      )}
    </div>
  )
}

function TaskRow({ item }: { item: TaskItem }) {
  const { selectedStep, setSelectedStep } = useAgentStore()
  if (item.children) return <GroupRow item={item} />
  const detail = detailOf(item)
  const selected = !!selectedStep && [item.call?.id, item.result?.id].includes(selectedStep.id)
  const running = item.status === 'running'
  const failed = item.status === 'failed'
  const done = item.status === 'done'

  const box = running
    ? 'border-accent-primary bg-accent-primary/10'
    : failed
      ? 'border-accent-red/40 bg-surface-secondary'
      : selected
        ? 'border-border-light bg-surface-active'
        : 'border-border bg-surface-secondary hover:bg-surface-hover'

  return (
    <button
      onClick={() => detail && setSelectedStep(selected ? null : detail)}
      aria-current={running ? 'step' : undefined}
      className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-[var(--radius-lg)] border text-left cursor-pointer transition-colors ${box}`}
    >
      <span className="flex-shrink-0" aria-hidden>
        {running ? (
          <Loader2 size={15} className="animate-spin text-accent-primary" />
        ) : failed ? (
          <AlertCircle size={15} className="text-accent-red" />
        ) : (
          <CheckCircle2 size={15} className="text-accent-green" />
        )}
      </span>
      <span className="min-w-0 flex-1">
        <span className={`block text-[13px] font-medium truncate ${done ? 'line-through text-content-tertiary' : failed ? 'text-accent-red' : 'text-content-primary'}`}>
          {item.label}
        </span>
        {item.summary && (
          <span className={`block text-xs truncate ${done ? 'line-through text-content-muted' : 'text-content-secondary'}`} title={item.summary}>
            {item.summary}
          </span>
        )}
      </span>
      {running && <span className="flex-shrink-0 text-[11px] px-2 py-0.5 rounded-full bg-accent-primary/20 text-accent-primary">진행 중</span>}
      {failed && <span className="flex-shrink-0 text-[11px] px-2 py-0.5 rounded-full bg-accent-red/15 text-accent-red">실패</span>}
      <ChevronRight size={13} className="flex-shrink-0 text-content-muted" aria-hidden />
    </button>
  )
}

/** 작업 항목 목록 (단계 안에서 쓴다): 합친 줄·위임은 접이식 행으로, 나머지는 목적 제목이 있는 한 줄로 */
function ItemList({ items }: { items: TaskItem[] }) {
  return (
    <ul className="space-y-0.5">
      {items.map((it) =>
        it.children ? (
          <li key={it.key}>
            <GroupRow item={it} />
          </li>
        ) : (
          <ChildRow key={it.key} item={it} showLabel />
        )
      )}
    </ul>
  )
}

/** 작업 계획: 실행 전에 만든 전체 단계. 단계를 펼치면 그 단계에서 한 상세 작업이 보인다. */
function PlanTree({ todos, running, pre, byStep }: { todos: TodoItem[]; running: boolean; pre: TaskItem[]; byStep: Record<string, TaskItem[]> }) {
  const [toggled, setToggled] = useState<Record<string, boolean>>({})
  const hasActive = todos.some((t) => t.status === 'in_progress')
  const preKey = '__pre'
  const preOpen = toggled[preKey] ?? (running && !hasActive)
  return (
    <div className="space-y-2" aria-label="작업 계획" role="group">
      {pre.length > 0 && (
        <div className="rounded-[var(--radius-lg)] border border-border bg-surface-secondary">
          <button onClick={() => setToggled((m) => ({ ...m, [preKey]: !preOpen }))} aria-expanded={preOpen} className="w-full flex items-center gap-2 px-3 py-2 text-[13px] text-left border-none bg-transparent cursor-pointer text-content-secondary">
            <ChevronRight size={13} className={`flex-shrink-0 transition-transform ${preOpen ? 'rotate-90' : ''}`} aria-hidden />
            준비 작업 <span className="text-content-muted">· {pre.length}개</span>
          </button>
          {preOpen && <div className="px-2 pb-2"><ItemList items={pre} /></div>}
        </div>
      )}
      <ol className="space-y-1.5 p-3 rounded-[var(--radius-lg)] border border-border bg-surface-secondary" aria-label="작업 계획 단계">
        {todos.map((t, i) => {
          const done = t.status === 'completed'
          const active = t.status === 'in_progress'
          const kids = byStep[t.id] ?? []
          const open = toggled[t.id] ?? (active && running)
          return (
            <li key={t.id} aria-current={active && running ? 'step' : undefined} className="text-[13px]">
              <button
                onClick={() => kids.length && setToggled((m) => ({ ...m, [t.id]: !open }))}
                aria-expanded={kids.length ? open : undefined}
                className={`w-full flex items-start gap-2 text-left border-none bg-transparent p-0 ${kids.length ? 'cursor-pointer' : 'cursor-default'}`}
              >
                <span className="mt-0.5 flex-shrink-0" aria-hidden>
                  {done ? (
                    <CheckCircle2 size={14} className="text-accent-green" />
                  ) : active ? (
                    running ? <Loader2 size={14} className="animate-spin text-accent-primary" /> : <Circle size={14} className="text-accent-primary" />
                  ) : (
                    <Circle size={14} className="text-content-muted" />
                  )}
                </span>
                <span className={`flex-1 min-w-0 ${done ? 'line-through text-content-tertiary' : active ? 'text-content-primary font-medium' : 'text-content-secondary'}`}>
                  <span className="text-content-muted mr-1.5">{i + 1}.</span>
                  {t.content}
                </span>
                {kids.length > 0 && <span className="flex-shrink-0 text-[11px] text-content-muted">작업 {kids.length}</span>}
                {active && running && <span className="flex-shrink-0 text-[11px] px-2 py-0.5 rounded-full bg-accent-primary/20 text-accent-primary">진행 중</span>}
                {kids.length > 0 && <ChevronRight size={12} className={`mt-1 flex-shrink-0 text-content-muted transition-transform ${open ? 'rotate-90' : ''}`} aria-hidden />}
              </button>
              {open && kids.length > 0 && (
                <div className="mt-1.5 ml-5 pl-2 border-l border-border">
                  <ItemList items={kids} />
                </div>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

/**
 * 우측 패널: 에이전트의 작업 진행 목록.
 * 도구 호출과 그 결과는 한 줄로 합치고, 끝난 작업은 취소선으로, 지금 하는 작업은 강조해서 보여 준다.
 * 실행 중에는 새 작업을 따라 아래로 스크롤한다.
 */
export default function StepsPanel({ steps, running }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const todos = useMemo(() => extractLatestTodos(steps), [steps])
  // 작업 계획이 있으면 todo 호출 행은 계획 목록과 겹치므로 숨긴다
  const items = useMemo(() => buildTaskItems(steps).filter((i) => !(todos && i.tool === 'todo')), [steps, todos])
  // 계획이 있으면 작업을 계획 단계 아래로 나눠 보여 준다
  const buckets = useMemo(() => (todos ? buildPlanBuckets(steps, todos.map((t) => t.id)) : null), [steps, todos])
  const current = running ? currentTask(items) : null
  const planStep = todos?.find((t) => t.status === 'in_progress')
  const finished = todos ? todos.filter((t) => t.status === 'completed').length : items.filter((i) => i.status !== 'running').length
  const total = todos ? todos.length : items.length

  useEffect(() => {
    if (running) bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [items.length, current?.key, running])

  return (
    <div className="p-4 space-y-3">
      <div className="flex items-start gap-2 text-[13px]">
        <span className="mt-0.5 flex-shrink-0">
          {running ? <Loader2 size={14} className="animate-spin text-accent-primary" /> : <CheckCircle2 size={14} className="text-accent-green" />}
        </span>
        <div className="min-w-0 flex-1">
          {running ? (
            // 지금 하는 작업은 아래 목록에서 강조해 보여 주므로 여기서는 상태만 알린다
            <div className="text-content-primary font-medium">{current || planStep ? '작업 중' : '답변을 정리하는 중…'}</div>
          ) : (
            <div className="text-content-secondary">작업 완료</div>
          )}
        </div>
        <span className="text-xs text-content-tertiary flex-shrink-0">완료 {finished} / {total}</span>
      </div>

      {todos && buckets && <PlanTree todos={todos} running={running} pre={buckets.pre} byStep={buckets.byStep} />}

      {todos ? null : items.length === 0 ? (
        <div className="text-center text-[13px] text-content-muted py-10 border border-dashed border-border rounded-[var(--radius-lg)]">
          아직 진행 내역이 없습니다.
          <div className="text-xs mt-1">에이전트가 도구를 쓰거나 분석하면 여기에 작업이 쌓입니다.</div>
        </div>
      ) : (
        <ol className="space-y-2">
          {items.map((item) => (
            <li key={item.key}>
              <TaskRow item={item} />
            </li>
          ))}
        </ol>
      )}
      <div ref={bottomRef} />
    </div>
  )
}

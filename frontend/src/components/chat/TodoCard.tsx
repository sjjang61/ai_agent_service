import { CheckCircle2, Circle, Loader2 } from 'lucide-react'
import type { AgentStepData } from '../../types/chat'

export interface TodoItem {
  id: string
  content: string
  status: 'pending' | 'in_progress' | 'completed'
}

/** todo 도구의 가장 최근 성공 결과를 꺼낸다. */
export function extractLatestTodos(steps: AgentStepData[] | undefined): TodoItem[] | null {
  let latest: TodoItem[] | null = null
  for (const s of steps ?? []) {
    if (s.type !== 'tool_result' || s.tool !== 'todo' || typeof s.output !== 'string') continue
    try {
      const p = JSON.parse(s.output)
      if (p?.ok && Array.isArray(p.todos)) latest = p.todos as TodoItem[]
    } catch {
      // 오류 문장은 무시
    }
  }
  return latest
}

export type PlanOutcome = 'running' | 'completed' | 'stopped'

const CANCEL_MARK = '사용자가 실행을 중단했습니다'

/** 응답의 끝난 상태: 실행 중 / 최종 답변까지 정상 완료 / 오류·중단·답변 없음으로 멈춤 */
export function planOutcome(content: string | undefined, running: boolean): PlanOutcome {
  if (running) return 'running'
  const text = (content ?? '').trim()
  return text && text !== '__error__' && !text.includes(CANCEL_MARK) ? 'completed' : 'stopped'
}

/**
 * 화면에 보여 줄 계획. 응답이 정상 완료됐으면 남은 단계도 완료로 본다 (서버가 같은 규칙으로 마무리하지만,
 * 그 전에 저장된 이력이나 갱신이 빠진 경우에도 계획이 중간 단계에 멈춰 보이지 않게 한다).
 */
export function settleTodos(todos: TodoItem[], outcome: PlanOutcome): TodoItem[] {
  if (outcome !== 'completed') return todos
  return todos.map((t) => (t.status === 'completed' ? t : { ...t, status: 'completed' as const }))
}

export default function TodoCard({ todos, running = true }: { todos: TodoItem[]; running?: boolean }) {
  const done = todos.filter((t) => t.status === 'completed').length
  const progress = (done / Math.max(todos.length, 1)) * 100
  const allDone = todos.length > 0 && done === todos.length

  return (
    <div className="mb-3 rounded-[var(--radius-lg)] border border-border bg-surface-secondary p-4 shadow-sm">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-content-primary flex items-center gap-2">
          <span className="text-accent-primary">📋</span>
          작업 계획
        </h4>
        <span
          className={`text-xs font-medium px-2 py-1 rounded-md transition-colors ${
            allDone ? 'bg-accent-done/15 text-accent-done' : 'bg-surface-tertiary text-content-secondary'
          }`}
        >
          {done}/{todos.length} 완료
        </span>
      </div>

      {/* 진행 바 */}
      <div className="h-2 rounded-full bg-surface-tertiary mb-3 overflow-hidden">
        <div
          className={`h-full transition-all duration-500 ease-out ${
            allDone ? 'bg-accent-done' : 'bg-gradient-to-r from-accent-primary to-accent-done'
          }`}
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* 작업 목록 */}
      <ul className="space-y-2">
        {todos.map((t) => (
          <li
            key={t.id}
            className={`flex items-start gap-2.5 text-sm p-2 rounded-md transition-all duration-200 ${
              t.status === 'completed'
                ? 'bg-accent-done/5 hover:bg-accent-done/10'
                : t.status === 'in_progress' && running
                ? 'bg-accent-primary/5 hover:bg-accent-primary/10'
                : 'hover:bg-surface-tertiary/50'
            }`}
          >
            {t.status === 'completed' ? (
              <CheckCircle2
                size={16}
                className="text-accent-done mt-0.5 flex-shrink-0 animate-check"
                strokeWidth={2.5}
              />
            ) : t.status === 'in_progress' && running ? (
              <Loader2 size={16} className="text-accent-primary mt-0.5 flex-shrink-0 animate-spin" />
            ) : (
              <Circle size={16} className="text-content-muted mt-0.5 flex-shrink-0" strokeWidth={2} />
            )}
            <span
              className={
                t.status === 'completed'
                  ? 'text-content-secondary line-through decoration-accent-done/40 decoration-2'
                  : t.status === 'in_progress' && running
                  ? 'text-content-primary font-medium'
                  : 'text-content-secondary'
              }
            >
              {t.content}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

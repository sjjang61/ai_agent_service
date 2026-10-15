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

export default function TodoCard({ todos }: { todos: TodoItem[] }) {
  const done = todos.filter((t) => t.status === 'completed').length
  const progress = (done / Math.max(todos.length, 1)) * 100

  return (
    <div className="mb-3 rounded-[var(--radius-lg)] border border-border bg-surface-secondary p-4 shadow-sm">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-content-primary flex items-center gap-2">
          <span className="text-accent-primary">📋</span>
          작업 계획
        </h4>
        <span className="text-xs font-medium text-content-secondary px-2 py-1 rounded-md bg-surface-tertiary">
          {done}/{todos.length} 완료
        </span>
      </div>

      {/* 진행 바 */}
      <div className="h-2 rounded-full bg-surface-tertiary mb-3 overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-accent-primary to-accent-blue transition-all duration-500 ease-out"
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
                ? 'bg-accent-green/5 hover:bg-accent-green/10'
                : t.status === 'in_progress'
                ? 'bg-accent-primary/5 hover:bg-accent-primary/10'
                : 'hover:bg-surface-tertiary/50'
            }`}
          >
            {t.status === 'completed' ? (
              <CheckCircle2
                size={16}
                className="text-accent-green mt-0.5 flex-shrink-0 animate-check"
                strokeWidth={2.5}
              />
            ) : t.status === 'in_progress' ? (
              <Loader2 size={16} className="text-accent-primary mt-0.5 flex-shrink-0 animate-spin" />
            ) : (
              <Circle size={16} className="text-content-muted mt-0.5 flex-shrink-0" strokeWidth={2} />
            )}
            <span
              className={
                t.status === 'completed'
                  ? 'text-content-secondary line-through decoration-accent-green/40 decoration-2'
                  : t.status === 'in_progress'
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

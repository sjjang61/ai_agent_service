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
  return (
    <div className="mb-3 rounded-xl border border-slate-600 bg-slate-900/60 p-3">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-semibold text-slate-100">작업 계획</h4>
        <span className="text-xs text-slate-400">
          {done}/{todos.length} 완료
        </span>
      </div>
      <div className="h-1 rounded bg-slate-700 mb-2 overflow-hidden">
        <div className="h-full bg-green-400 transition-all" style={{ width: `${(done / Math.max(todos.length, 1)) * 100}%` }} />
      </div>
      <ul className="space-y-1">
        {todos.map((t) => (
          <li key={t.id} className="flex items-start gap-2 text-sm">
            {t.status === 'completed' ? (
              <CheckCircle2 size={15} className="text-green-400 mt-0.5 flex-shrink-0" />
            ) : t.status === 'in_progress' ? (
              <Loader2 size={15} className="text-blue-400 mt-0.5 flex-shrink-0 animate-spin" />
            ) : (
              <Circle size={15} className="text-slate-500 mt-0.5 flex-shrink-0" />
            )}
            <span
              className={
                t.status === 'completed'
                  ? 'text-slate-500 line-through'
                  : t.status === 'in_progress'
                  ? 'text-slate-100 font-medium'
                  : 'text-slate-300'
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

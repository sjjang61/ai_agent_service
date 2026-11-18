import { Loader2 } from 'lucide-react'
import { ACTIVE, STATUS_LABEL, type RunStatus } from '../../api/functions'

const STYLE: Record<RunStatus, string> = {
  queued: 'bg-surface-tertiary text-content-secondary',
  starting: 'bg-accent-primary/15 text-accent-primary',
  running: 'bg-accent-primary/15 text-accent-primary',
  succeeded: 'bg-accent-green/15 text-accent-green',
  failed: 'bg-accent-red/15 text-accent-red',
  timeout: 'bg-accent-amber/15 text-accent-amber',
  cancelled: 'bg-surface-tertiary text-content-tertiary',
  rejected: 'bg-accent-red/10 text-accent-red',
}

/** 실행 상태 배지. 색에만 의존하지 않도록 항상 글자를 함께 보인다 */
export default function StatusBadge({ status }: { status: RunStatus | null | undefined }) {
  if (!status) return <span className="text-xs text-content-tertiary">실행 기록 없음</span>
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium whitespace-nowrap ${STYLE[status]}`}>
      {ACTIVE.includes(status) && <Loader2 size={10} className="animate-spin" aria-hidden />}
      {STATUS_LABEL[status]}
    </span>
  )
}

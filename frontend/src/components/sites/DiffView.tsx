import { lineDiff } from '../../utils/lineDiff'

/** 줄 단위 비교 표시: 지운 줄은 빨강(−), 더한 줄은 초록(+). 바뀌지 않은 긴 구간은 접어서 보여 준다. */
export default function DiffView({ before, after, empty = '변경 없음' }: { before: string; after: string; empty?: string }) {
  const lines = lineDiff(before, after)
  if (!lines.some((l) => l.kind !== 'same')) return <p className="text-xs text-content-tertiary">{empty}</p>
  const keep = new Set<number>()
  lines.forEach((l, i) => { if (l.kind !== 'same') for (let k = i - 2; k <= i + 2; k++) keep.add(k) })
  const rows: React.ReactNode[] = []
  let skipped = 0
  lines.forEach((l, i) => {
    if (!keep.has(i)) { skipped++; return }
    if (skipped) { rows.push(<div key={`s${i}`} className="px-2 text-content-muted">⋯ {skipped}줄 동일</div>); skipped = 0 }
    const cls = l.kind === 'add' ? 'bg-green-500/10 text-green-600' : l.kind === 'del' ? 'bg-red-500/10 text-red-500' : 'text-content-secondary'
    rows.push(<div key={i} className={`px-2 whitespace-pre-wrap break-words ${cls}`}>{l.kind === 'add' ? '+ ' : l.kind === 'del' ? '− ' : '  '}{l.text || ' '}</div>)
  })
  if (skipped) rows.push(<div key="end" className="px-2 text-content-muted">⋯ {skipped}줄 동일</div>)
  return <div className="font-mono text-[12px] leading-relaxed border border-border rounded-[var(--radius-md)] py-1 max-h-[320px] overflow-y-auto bg-surface-secondary">{rows}</div>
}

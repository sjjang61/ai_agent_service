import type { StatsSpec } from '../../types/widget'

const TONE: Record<string, string> = {
  default: 'text-content-primary',
  positive: 'text-accent-green',
  negative: 'text-accent-red',
  accent: 'text-accent-primary',
}

// Tailwind 는 동적 클래스명을 찾지 못하므로 열 수별 클래스를 고정해 둔다
const COLS: Record<number, string> = {
  1: 'grid-cols-1',
  2: 'grid-cols-1 sm:grid-cols-2',
  3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
  4: 'grid-cols-2 lg:grid-cols-4',
}

/** 핵심 수치 카드: 라벨 · 큰 값 · 보조 설명 */
export default function StatsWidget({ spec }: { spec: StatsSpec }) {
  const cols = spec.columns ?? (spec.items.length <= 4 ? 2 : 3)
  return (
    <div>
      <div className={`grid gap-3 ${COLS[cols] ?? COLS[2]}`}>
        {spec.items.map((it, i) => (
          <div key={i} className="rounded-[var(--radius-lg)] border border-border bg-surface-primary px-5 py-4">
            <div className="text-[13px] text-content-secondary">{it.label}</div>
            <div className={`mt-1 text-[30px] leading-tight font-bold tracking-tight ${TONE[it.tone ?? 'default']}`}>
              {it.value}
            </div>
            {it.note && <div className="mt-0.5 text-[13px] text-content-tertiary">{it.note}</div>}
          </div>
        ))}
      </div>
      {spec.caption && <p className="mt-2 text-xs text-content-tertiary">{spec.caption}</p>}
    </div>
  )
}

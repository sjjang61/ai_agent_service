import type { ChartSpec } from '../../types/widget'

const COLORS = ['#60a5fa', '#34d399', '#fbbf24', '#f87171', '#a78bfa', '#22d3ee', '#fb923c', '#f472b6', '#a3e635', '#94a3b8']
const W = 560
const H = 260
const M = { top: 16, right: 16, bottom: 44, left: 48 }

function niceMax(v: number) {
  if (v <= 0) return 1
  const p = Math.pow(10, Math.floor(Math.log10(v)))
  const n = v / p
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p
}

const fmt = (n: number) => (Math.abs(n) >= 1000 ? n.toLocaleString() : String(Math.round(n * 100) / 100))

function Legend({ names }: { names: string[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-slate-300">
      {names.map((n, i) => (
        <span key={i} className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm" style={{ background: COLORS[i % COLORS.length] }} />
          {n}
        </span>
      ))}
    </div>
  )
}

function Axes({ max, unit }: { max: number; unit?: string }) {
  const ticks = [0, 0.25, 0.5, 0.75, 1]
  const plotH = H - M.top - M.bottom
  return (
    <g>
      {ticks.map((t) => {
        const y = M.top + plotH * (1 - t)
        return (
          <g key={t}>
            <line x1={M.left} x2={W - M.right} y1={y} y2={y} stroke="#334155" strokeWidth={1} />
            <text x={M.left - 6} y={y + 3} textAnchor="end" fontSize={10} fill="#94a3b8">
              {fmt(max * t)}
            </text>
          </g>
        )
      })}
      {unit && (
        <text x={M.left} y={10} fontSize={10} fill="#94a3b8">
          ({unit})
        </text>
      )}
    </g>
  )
}

function XLabels({ labels }: { labels: string[] }) {
  const plotW = W - M.left - M.right
  const step = plotW / labels.length
  const skip = Math.ceil(labels.length / 12)
  return (
    <g>
      {labels.map((l, i) =>
        i % skip === 0 ? (
          <text key={i} x={M.left + step * (i + 0.5)} y={H - M.bottom + 16} textAnchor="middle" fontSize={10} fill="#cbd5e1">
            {l.length > 10 ? l.slice(0, 9) + '…' : l}
          </text>
        ) : null
      )}
    </g>
  )
}

function Bars({ spec }: { spec: ChartSpec }) {
  const max = niceMax(Math.max(...spec.series.flatMap((s) => s.values), 0))
  const plotW = W - M.left - M.right
  const plotH = H - M.top - M.bottom
  const groupW = plotW / spec.labels.length
  const barW = Math.min((groupW * 0.8) / spec.series.length, 48)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">
      <Axes max={max} unit={spec.unit} />
      {spec.labels.map((_, i) =>
        spec.series.map((s, j) => {
          const v = Math.max(s.values[i] ?? 0, 0)
          const h = (v / max) * plotH
          const x = M.left + groupW * i + (groupW - barW * spec.series.length) / 2 + barW * j
          return (
            <rect key={`${i}-${j}`} x={x} y={M.top + plotH - h} width={barW - 2} height={h} rx={2} fill={COLORS[j % COLORS.length]}>
              <title>{`${s.name} · ${spec.labels[i]}: ${fmt(s.values[i] ?? 0)}${spec.unit ?? ''}`}</title>
            </rect>
          )
        })
      )}
      <XLabels labels={spec.labels} />
    </svg>
  )
}

function Lines({ spec }: { spec: ChartSpec }) {
  const all = spec.series.flatMap((s) => s.values)
  const max = niceMax(Math.max(...all, 0))
  const plotW = W - M.left - M.right
  const plotH = H - M.top - M.bottom
  const step = plotW / spec.labels.length
  const pt = (i: number, v: number) => [M.left + step * (i + 0.5), M.top + plotH * (1 - Math.max(v, 0) / max)]
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">
      <Axes max={max} unit={spec.unit} />
      {spec.series.map((s, j) => (
        <g key={j}>
          <polyline
            fill="none"
            stroke={COLORS[j % COLORS.length]}
            strokeWidth={2}
            points={s.values.map((v, i) => pt(i, v).join(',')).join(' ')}
          />
          {s.values.map((v, i) => {
            const [x, y] = pt(i, v)
            return (
              <circle key={i} cx={x} cy={y} r={3.5} fill={COLORS[j % COLORS.length]}>
                <title>{`${s.name} · ${spec.labels[i]}: ${fmt(v)}${spec.unit ?? ''}`}</title>
              </circle>
            )
          })}
        </g>
      ))}
      <XLabels labels={spec.labels} />
    </svg>
  )
}

function Pie({ spec }: { spec: ChartSpec }) {
  const values = (spec.series[0]?.values ?? []).map((v) => Math.max(v, 0))
  const total = values.reduce((a, b) => a + b, 0) || 1
  const R = 90
  const cx = 110
  const cy = 110
  let acc = 0
  const slices = values.map((v, i) => {
    const a0 = (acc / total) * Math.PI * 2 - Math.PI / 2
    acc += v
    const a1 = (acc / total) * Math.PI * 2 - Math.PI / 2
    const large = a1 - a0 > Math.PI ? 1 : 0
    const p = (a: number) => `${cx + R * Math.cos(a)} ${cy + R * Math.sin(a)}`
    const d =
      values.length === 1
        ? `M ${cx - R} ${cy} a ${R} ${R} 0 1 0 ${R * 2} 0 a ${R} ${R} 0 1 0 ${-R * 2} 0`
        : `M ${cx} ${cy} L ${p(a0)} A ${R} ${R} 0 ${large} 1 ${p(a1)} Z`
    return { d, v, i }
  })
  return (
    <div className="flex flex-wrap items-center gap-4">
      <svg viewBox="0 0 220 220" className="w-48 h-48 flex-shrink-0">
        {slices.map((s) => (
          <path key={s.i} d={s.d} fill={COLORS[s.i % COLORS.length]} stroke="#1e293b" strokeWidth={1.5}>
            <title>{`${spec.labels[s.i]}: ${fmt(s.v)}${spec.unit ?? ''} (${Math.round((s.v / total) * 100)}%)`}</title>
          </path>
        ))}
      </svg>
      <ul className="text-xs text-slate-300 space-y-1">
        {slices.map((s) => (
          <li key={s.i} className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: COLORS[s.i % COLORS.length] }} />
            {spec.labels[s.i]} — {fmt(s.v)}
            {spec.unit ?? ''} ({Math.round((s.v / total) * 100)}%)
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function ChartWidget({ spec }: { spec: ChartSpec }) {
  return (
    <div>
      {spec.chart_type === 'bar' && <Bars spec={spec} />}
      {spec.chart_type === 'line' && <Lines spec={spec} />}
      {spec.chart_type === 'pie' && <Pie spec={spec} />}
      {spec.chart_type !== 'pie' && spec.series.length > 1 && <Legend names={spec.series.map((s) => s.name)} />}
    </div>
  )
}

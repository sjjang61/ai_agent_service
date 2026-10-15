import { Download } from 'lucide-react'
import { useRef } from 'react'
import type { ChartSpec } from '../../types/widget'

const COLORS = ['#60a5fa', '#34d399', '#fbbf24', '#f87171', '#a78bfa', '#22d3ee', '#fb923c', '#f472b6', '#a3e635', '#94a3b8']
const W = 560
const H = 260
const M = { top: 16, right: 16, bottom: 44, left: 70 } // left 마진 증가: 큰 숫자 표시
const M_WITH_TITLE = { top: 40, right: 16, bottom: 44, left: 70 } // 제목 있을 때
const FONT_FAMILY = '-apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", Roboto, "Helvetica Neue", Arial, sans-serif'

// SVG를 PNG로 다운로드하는 함수
function downloadSvgAsPng(svgElement: SVGSVGElement, filename: string) {
  const svgData = new XMLSerializer().serializeToString(svgElement)
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  const img = new Image()

  // SVG의 viewBox에서 크기 추출
  const viewBox = svgElement.getAttribute('viewBox')
  const [, , width, height] = viewBox ? viewBox.split(' ').map(Number) : [0, 0, W, H]

  // 2배 해상도로 렌더링 (더 선명하게)
  canvas.width = width * 2
  canvas.height = height * 2

  img.onload = () => {
    if (!ctx) return
    // 흰색 배경 추가 (투명 배경 대신)
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    // 이미지 그리기
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    // PNG로 변환 및 다운로드
    canvas.toBlob((blob) => {
      if (!blob) return
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    })
  }

  img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)))
}

function niceMax(v: number) {
  if (v <= 0) return 1
  const p = Math.pow(10, Math.floor(Math.log10(v)))
  const n = v / p
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p
}

const fmt = (n: number) => (Math.abs(n) >= 1000 ? n.toLocaleString() : String(Math.round(n * 100) / 100))

function Legend({ names }: { names: string[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-content-secondary">
      {names.map((n, i) => (
        <span key={i} className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm" style={{ background: COLORS[i % COLORS.length] }} />
          {n}
        </span>
      ))}
    </div>
  )
}

function Axes({ max, unit, margin }: { max: number; unit?: string; margin: typeof M }) {
  const ticks = [0, 0.25, 0.5, 0.75, 1]
  const plotH = H - margin.top - margin.bottom
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
  const gridColor = isDark ? '#334155' : '#e2e8f0'
  const textColor = isDark ? '#94a3b8' : '#64748b'

  return (
    <g>
      {ticks.map((t) => {
        const y = margin.top + plotH * (1 - t)
        return (
          <g key={t}>
            <line x1={margin.left} x2={W - margin.right} y1={y} y2={y} stroke={gridColor} strokeWidth={1} />
            <text x={margin.left - 6} y={y + 3} textAnchor="end" fontSize={10} fill={textColor} fontFamily={FONT_FAMILY}>
              {fmt(max * t)}
            </text>
          </g>
        )
      })}
      {unit && (
        <text x={margin.left} y={margin.top - 5} fontSize={10} fill={textColor} fontFamily={FONT_FAMILY}>
          ({unit})
        </text>
      )}
    </g>
  )
}

function XLabels({ labels, margin }: { labels: string[]; margin: typeof M }) {
  const plotW = W - margin.left - margin.right
  const step = plotW / labels.length
  const skip = Math.ceil(labels.length / 12)
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
  const labelColor = isDark ? '#cbd5e1' : '#475569'

  return (
    <g>
      {labels.map((l, i) =>
        i % skip === 0 ? (
          <text key={i} x={margin.left + step * (i + 0.5)} y={H - margin.bottom + 16} textAnchor="middle" fontSize={10} fill={labelColor} fontFamily={FONT_FAMILY}>
            {l.length > 10 ? l.slice(0, 9) + '…' : l}
          </text>
        ) : null
      )}
    </g>
  )
}

function Bars({ spec, title }: { spec: ChartSpec; title?: string }) {
  const margin = title ? M_WITH_TITLE : M
  const max = niceMax(Math.max(...spec.series.flatMap((s) => s.values), 0))
  const plotW = W - margin.left - margin.right
  const plotH = H - margin.top - margin.bottom
  const groupW = plotW / spec.labels.length
  const barW = Math.min((groupW * 0.8) / spec.series.length, 48)
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
  const titleColor = isDark ? '#e2e8f0' : '#1e293b'

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" style={{ fontFamily: FONT_FAMILY }}>
      {title && (
        <text x={W / 2} y={20} textAnchor="middle" fontSize={14} fontWeight="600" fill={titleColor} fontFamily={FONT_FAMILY}>
          {title}
        </text>
      )}
      <Axes max={max} unit={spec.unit} margin={margin} />
      {spec.labels.map((_, i) =>
        spec.series.map((s, j) => {
          const v = Math.max(s.values[i] ?? 0, 0)
          const h = (v / max) * plotH
          const x = margin.left + groupW * i + (groupW - barW * spec.series.length) / 2 + barW * j
          return (
            <rect key={`${i}-${j}`} x={x} y={margin.top + plotH - h} width={barW - 2} height={h} rx={2} fill={COLORS[j % COLORS.length]}>
              <title>{`${s.name} · ${spec.labels[i]}: ${fmt(s.values[i] ?? 0)}${spec.unit ?? ''}`}</title>
            </rect>
          )
        })
      )}
      <XLabels labels={spec.labels} margin={margin} />
    </svg>
  )
}

function Lines({ spec, title }: { spec: ChartSpec; title?: string }) {
  const margin = title ? M_WITH_TITLE : M
  const all = spec.series.flatMap((s) => s.values)
  const max = niceMax(Math.max(...all, 0))
  const plotW = W - margin.left - margin.right
  const plotH = H - margin.top - margin.bottom
  const step = plotW / spec.labels.length
  const pt = (i: number, v: number) => [margin.left + step * (i + 0.5), margin.top + plotH * (1 - Math.max(v, 0) / max)]
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
  const titleColor = isDark ? '#e2e8f0' : '#1e293b'

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" style={{ fontFamily: FONT_FAMILY }}>
      {title && (
        <text x={W / 2} y={20} textAnchor="middle" fontSize={14} fontWeight="600" fill={titleColor} fontFamily={FONT_FAMILY}>
          {title}
        </text>
      )}
      <Axes max={max} unit={spec.unit} margin={margin} />
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
      <XLabels labels={spec.labels} margin={margin} />
    </svg>
  )
}

function Pie({ spec, title }: { spec: ChartSpec; title?: string }) {
  const values = (spec.series[0]?.values ?? []).map((v) => Math.max(v, 0))
  const total = values.reduce((a, b) => a + b, 0) || 1
  const R = 90
  const cx = 110
  const cy = 110
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
  const strokeColor = isDark ? '#1e293b' : '#f1f5f9'
  const titleColor = isDark ? '#e2e8f0' : '#1e293b'

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
    <div>
      {title && (
        <h4 className="text-sm font-semibold text-content-primary mb-3">{title}</h4>
      )}
      <div className="flex flex-wrap items-center gap-4">
        <svg viewBox="0 0 220 220" className="w-48 h-48 flex-shrink-0" style={{ fontFamily: FONT_FAMILY }}>
          {slices.map((s) => (
            <path key={s.i} d={s.d} fill={COLORS[s.i % COLORS.length]} stroke={strokeColor} strokeWidth={1.5}>
              <title>{`${spec.labels[s.i]}: ${fmt(s.v)}${spec.unit ?? ''} (${Math.round((s.v / total) * 100)}%)`}</title>
            </path>
          ))}
        </svg>
        <ul className="text-xs text-content-secondary space-y-1">
          {slices.map((s) => (
            <li key={s.i} className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ background: COLORS[s.i % COLORS.length] }} />
              {spec.labels[s.i]} — {fmt(s.v)}
              {spec.unit ?? ''} ({Math.round((s.v / total) * 100)}%)
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export default function ChartWidget({ spec, title }: { spec: ChartSpec; title?: string }) {
  const svgRef = useRef<SVGSVGElement>(null)

  const handleDownload = () => {
    if (!svgRef.current) return
    const filename = `chart-${spec.chart_type}-${Date.now()}.png`
    downloadSvgAsPng(svgRef.current, filename)
  }

  return (
    <div className="relative group">
      <button
        onClick={handleDownload}
        className="absolute top-2 right-2 p-2 rounded-lg bg-surface-tertiary border border-border hover:bg-surface-hover transition-colors opacity-0 group-hover:opacity-100 z-10"
        title="차트를 PNG 이미지로 다운로드"
      >
        <Download size={16} className="text-content-secondary" />
      </button>
      <div ref={(el) => {
        if (el && el.querySelector('svg')) {
          (svgRef as any).current = el.querySelector('svg')
        }
      }}>
        {spec.chart_type === 'bar' && <Bars spec={spec} title={title} />}
        {spec.chart_type === 'line' && <Lines spec={spec} title={title} />}
        {spec.chart_type === 'pie' && <Pie spec={spec} title={title} />}
      </div>
      {spec.chart_type !== 'pie' && spec.series.length > 1 && <Legend names={spec.series.map((s) => s.name)} />}
    </div>
  )
}

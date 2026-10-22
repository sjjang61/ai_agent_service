import { lazy, Suspense } from 'react'
import type { AgentStepData } from '../../types/chat'
import type { Widget } from '../../types/widget'
import TableWidget from './TableWidget'
import ChartWidget from './ChartWidget'
import StatsWidget from './StatsWidget'
import ProcessWidget from './ProcessWidget'

// mermaid / leaflet 은 용량이 커서 위젯이 실제로 나올 때만 불러온다
const FlowWidget = lazy(() => import('./FlowWidget'))
const MapWidget = lazy(() => import('./MapWidget'))

/** create_widget 의 성공한 tool_result 에서 위젯을 꺼낸다 (실시간·저장된 메시지 공통). */
export function extractWidgets(steps: AgentStepData[] | undefined): Widget[] {
  const widgets: Widget[] = []
  for (const s of steps ?? []) {
    if (s.type !== 'tool_result' || s.tool !== 'create_widget' || typeof s.output !== 'string') continue
    try {
      const parsed = JSON.parse(s.output)
      if (parsed?.ok && parsed.widget?.type && parsed.widget?.spec) widgets.push(parsed.widget as Widget)
    } catch {
      // 오류 문장 등 JSON 이 아닌 결과는 무시
    }
  }
  return widgets
}

function WidgetBody({ widget }: { widget: Widget }) {
  switch (widget.type) {
    case 'table':
      return <TableWidget spec={widget.spec} />
    case 'chart':
      return <ChartWidget spec={widget.spec} title={widget.title} />
    case 'flow':
      return (
        <Suspense fallback={<p className="text-xs text-content-muted">불러오는 중...</p>}>
          <FlowWidget spec={widget.spec} />
        </Suspense>
      )
    case 'map':
      return (
        <Suspense fallback={<p className="text-xs text-content-muted">지도를 불러오는 중...</p>}>
          <MapWidget spec={widget.spec} />
        </Suspense>
      )
    case 'stats':
      return <StatsWidget spec={widget.spec} />
    case 'process':
      return <ProcessWidget spec={widget.spec} />
    default:
      return null
  }
}

export default function WidgetRenderer({ widgets }: { widgets: Widget[] }) {
  if (widgets.length === 0) return null
  return (
    <div className="space-y-3 mb-3">
      {widgets.map((w, i) => (
        <div
          key={i}
          // 수치 카드·프로세스는 자체 테두리가 있어 바깥 상자 없이 제목만 붙인다
          className={
            w.type === 'stats' || w.type === 'process'
              ? ''
              : 'rounded-[var(--radius-lg)] border border-border bg-surface-secondary p-4 shadow-sm'
          }
        >
          {w.title && (
            <h4 className={`font-semibold text-content-primary ${w.type === 'stats' || w.type === 'process' ? 'text-[15px] mb-3' : 'text-sm mb-2'}`}>
              {w.title}
            </h4>
          )}
          <WidgetBody widget={w} />
        </div>
      ))}
    </div>
  )
}

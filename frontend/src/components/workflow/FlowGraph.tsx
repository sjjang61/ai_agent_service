import { memo, useCallback, useMemo, useRef, useState } from 'react'
import ReactFlow, { Background, BackgroundVariant, Controls, Handle, MarkerType, Position, type Edge, type Node, type NodeProps } from 'reactflow'
import 'reactflow/dist/style.css'
import './flowGraph.css'
import dagre from 'dagre'
import { Download } from 'lucide-react'
import { toPng } from 'html-to-image'
import type { NodeShape, ParsedFlow } from './mermaidFlow'

interface NodeData {
  label: string
  shape: NodeShape
  direction: 'TB' | 'LR'
}

const SHAPE_STYLE: Record<NodeShape, string> = {
  rect: 'rounded-[var(--radius-md)] border-border-light bg-surface-tertiary',
  round: 'rounded-[var(--radius-lg)] border-border-light bg-surface-tertiary',
  subroutine: 'rounded-[var(--radius-md)] border-accent-purple bg-surface-tertiary',
  database: 'rounded-[var(--radius-lg)] border-accent-cyan bg-surface-tertiary',
  hexagon: 'rounded-[var(--radius-lg)] border-accent-orange bg-surface-tertiary',
  flag: 'rounded-[var(--radius-md)] border-accent-yellow bg-surface-tertiary',
  decision: 'rounded-[var(--radius-md)] border-accent-amber bg-accent-amber/10',
  stadium: 'rounded-full border-accent-primary bg-accent-primary/10',
  circle: 'rounded-full border-accent-primary bg-accent-primary/10',
}

function FlowNodeView({ data }: NodeProps<NodeData>) {
  const vertical = data.direction === 'TB'
  return (
    <div className={`px-3.5 py-2 border-2 text-[13px] leading-snug text-content-primary text-center whitespace-pre-line break-words ${SHAPE_STYLE[data.shape]}`}>
      <Handle type="target" position={vertical ? Position.Top : Position.Left} isConnectable={false} />
      {data.shape === 'decision' && <span className="text-accent-amber mr-1" aria-hidden>◇</span>}
      {data.label}
      <Handle type="source" position={vertical ? Position.Bottom : Position.Right} isConnectable={false} />
    </div>
  )
}
const nodeTypes = { flowNode: memo(FlowNodeView) }

/** 라벨 길이로 노드 크기를 어림해 dagre 레이아웃에 넘긴다 */
function sizeOf(label: string): { w: number; h: number } {
  const lines = label.split('\n')
  const longest = Math.max(...lines.map((l) => [...l].reduce((n, ch) => n + (ch.charCodeAt(0) > 0x2e80 ? 1.9 : 1), 0)))
  const w = Math.min(260, Math.max(110, longest * 7.5 + 40))
  const wrapped = Math.max(lines.length, Math.ceil((longest * 7.5 + 40) / 260))
  return { w, h: 40 + (wrapped - 1) * 18 }
}

function layout(flow: ParsedFlow) {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: flow.direction, nodesep: 44, ranksep: 64, edgesep: 24, marginx: 16, marginy: 16 })
  const sizes = new Map(flow.nodes.map((n) => [n.id, sizeOf(n.label)]))
  flow.nodes.forEach((n) => g.setNode(n.id, { width: sizes.get(n.id)!.w, height: sizes.get(n.id)!.h }))
  const ids = new Set(flow.nodes.map((n) => n.id))
  // 엣지 라벨 자리를 레이아웃에 반영해 라벨이 노드와 겹치지 않게 한다
  flow.edges
    .filter((e) => ids.has(e.from) && ids.has(e.to))
    .forEach((e) => g.setEdge(e.from, e.to, e.label ? { width: Math.max(28, [...e.label].length * 9 + 14), height: 18, labelpos: 'c' } : {}))
  dagre.layout(g)

  const nodes: Node<NodeData>[] = flow.nodes.map((n) => {
    const p = g.node(n.id)
    const s = sizes.get(n.id)!
    return {
      id: n.id,
      type: 'flowNode',
      position: { x: p.x - s.w / 2, y: p.y - s.h / 2 },
      style: { width: s.w },
      data: { label: n.label, shape: n.shape, direction: flow.direction },
      draggable: false,
    }
  })
  const edges: Edge[] = flow.edges
    .filter((e) => ids.has(e.from) && ids.has(e.to))
    .map((e, i) => ({
      id: `e${i}-${e.from}-${e.to}`,
      source: e.from,
      target: e.to,
      label: e.label || undefined,
      type: 'smoothstep',
      animated: false,
      style: { strokeDasharray: e.dashed ? '6 4' : undefined, strokeWidth: e.thick ? 3 : 1.6 },
      markerEnd: e.arrow ? { type: MarkerType.ArrowClosed, width: 16, height: 16 } : undefined,
      labelBgPadding: [6, 3] as [number, number],
      labelBgBorderRadius: 4,
    }))
  const g0 = g.graph()
  return { nodes, edges, width: g0.width ?? 600, height: g0.height ?? 300 }
}

/** 응답 내용 속 흐름(절차·분기)을 그리는 React Flow 다이어그램. 에이전트의 실행 과정을 그리는 용도가 아니다. */
export default function FlowGraph({ flow }: { flow: ParsedFlow }) {
  const ref = useRef<HTMLDivElement>(null)
  const [exporting, setExporting] = useState(false)
  const { nodes, edges, height } = useMemo(() => layout(flow), [flow])
  const boxHeight = Math.min(560, Math.max(220, height + 40))

  const exportPng = useCallback(async () => {
    if (!ref.current) return
    setExporting(true)
    try {
      const bg = getComputedStyle(document.documentElement).getPropertyValue('--bg-secondary').trim() || '#ffffff'
      const url = await toPng(ref.current, { backgroundColor: bg, pixelRatio: 2 })
      const a = document.createElement('a')
      a.download = `flow-${Date.now()}.png`
      a.href = url
      a.click()
    } catch (e) {
      console.error('Failed to export flow:', e)
    } finally {
      setExporting(false)
    }
  }, [])

  return (
    <div ref={ref} className="flow-graph relative border border-border rounded-[var(--radius-lg)] overflow-hidden" style={{ height: boxHeight }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.3}
        maxZoom={1.6}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="var(--border-color)" />
        <Controls showInteractive={false} />
      </ReactFlow>
      <button
        onClick={exportPng}
        disabled={exporting}
        aria-label="흐름도를 PNG 로 저장"
        title="PNG 로 저장"
        className="absolute top-2 right-2 z-10 flex items-center gap-1.5 px-2.5 py-1.5 rounded-[var(--radius-md)] text-xs border border-border bg-surface-tertiary text-content-secondary hover:text-content-primary hover:bg-surface-hover cursor-pointer disabled:opacity-50"
      >
        <Download size={13} />
        {exporting ? '저장 중…' : 'PNG'}
      </button>
    </div>
  )
}

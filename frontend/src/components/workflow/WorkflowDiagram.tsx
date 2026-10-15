import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Panel,
  BackgroundVariant,
} from 'reactflow'
import 'reactflow/dist/style.css'
import './workflow.css'
import { Download } from 'lucide-react'
import { toPng } from 'html-to-image'

import type { AgentStepData } from '../../types/chat'
import { convertStepsToFlow, getLayoutedElements, getOptimalDirection } from './WorkflowConverter'
import ThoughtNode from './nodes/ThoughtNode'
import ToolCallNode from './nodes/ToolCallNode'
import ToolResultNode from './nodes/ToolResultNode'

// 커스텀 노드 타입 등록
const nodeTypes = {
  thoughtNode: ThoughtNode,
  toolCallNode: ToolCallNode,
  toolResultNode: ToolResultNode,
}

interface WorkflowDiagramProps {
  steps: AgentStepData[]
  height?: number
}

export default function WorkflowDiagram({ steps, height = 400 }: WorkflowDiagramProps) {
  const flowRef = useRef<HTMLDivElement>(null)
  const [isExporting, setIsExporting] = useState(false)

  // ReactFlow 상태
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  // 초기 레이아웃 계산
  useEffect(() => {
    const direction = getOptimalDirection(steps.length)
    const { nodes: initialNodes, edges: initialEdges } = convertStepsToFlow(steps)
    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
      initialNodes,
      initialEdges,
      direction
    )

    setNodes(layoutedNodes)
    setEdges(layoutedEdges)
  }, [steps, setNodes, setEdges])

  // 이미지 내보내기
  const handleExport = useCallback(async () => {
    if (!flowRef.current) return

    setIsExporting(true)

    try {
      const dataUrl = await toPng(flowRef.current, {
        backgroundColor: '#ffffff',
        quality: 1.0,
        pixelRatio: 2,
      })

      // 다운로드
      const link = document.createElement('a')
      link.download = `workflow-${Date.now()}.png`
      link.href = dataUrl
      link.click()
    } catch (error) {
      console.error('Failed to export workflow:', error)
    } finally {
      setIsExporting(false)
    }
  }, [])

  // MiniMap 노드 컬러
  const nodeColor = useCallback((node: any) => {
    switch (node.type) {
      case 'thoughtNode':
        return '#a855f7' // purple-500
      case 'toolCallNode':
        return '#3b82f6' // blue-500
      case 'toolResultNode':
        return '#10b981' // green-500
      default:
        return '#6b7280' // gray-500
    }
  }, [])

  return (
    <div
      ref={flowRef}
      className="border border-border rounded-[var(--radius-lg)] overflow-hidden bg-surface-secondary"
      style={{ height }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.5}
        maxZoom={1.5}
        attributionPosition="bottom-right"
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="var(--border)" />
        <Controls />
        <MiniMap nodeColor={nodeColor} nodeStrokeWidth={3} zoomable pannable />

        {/* 이미지 내보내기 버튼 */}
        <Panel position="top-right">
          <button
            onClick={handleExport}
            disabled={isExporting}
            className="flex items-center gap-2 px-3 py-2 bg-surface-tertiary border border-border rounded-lg text-sm font-medium text-content-primary hover:bg-surface-hover transition-colors disabled:opacity-50"
          >
            <Download size={16} />
            {isExporting ? 'Exporting...' : 'Export PNG'}
          </button>
        </Panel>
      </ReactFlow>
    </div>
  )
}

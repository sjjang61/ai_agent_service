import type { Node, Edge } from 'reactflow'
import type { AgentStepData } from '../../types/chat'
import dagre from 'dagre'

export interface WorkflowNodeData {
  step: AgentStepData
  index: number
}

/**
 * AgentStep 배열을 ReactFlow의 노드와 엣지로 변환
 */
export function convertStepsToFlow(steps: AgentStepData[]): {
  nodes: Node<WorkflowNodeData>[]
  edges: Edge[]
} {
  const nodes: Node<WorkflowNodeData>[] = []
  const edges: Edge[] = []

  steps.forEach((step, index) => {
    // 노드 타입 결정
    let nodeType = 'default'
    if (step.type === 'thought') {
      nodeType = 'thoughtNode'
    } else if (step.type === 'tool_call') {
      nodeType = 'toolCallNode'
    } else if (step.type === 'tool_result') {
      nodeType = 'toolResultNode'
    }

    // 노드 생성
    nodes.push({
      id: `step-${index}`,
      type: nodeType,
      data: { step, index },
      position: { x: 0, y: 0 }, // dagre로 자동 계산됨
    })

    // 이전 노드와 연결
    if (index > 0) {
      const prevStep = steps[index - 1]
      const isSuccess = step.type === 'tool_result' && step.output !== undefined

      edges.push({
        id: `edge-${index - 1}-${index}`,
        source: `step-${index - 1}`,
        target: `step-${index}`,
        animated: prevStep.type === 'tool_call', // tool_call 후 애니메이션
        style: {
          stroke: isSuccess ? 'var(--accent-primary)' : 'var(--border)',
          strokeWidth: 2,
        },
        type: 'smoothstep',
      })
    }
  })

  return { nodes, edges }
}

/**
 * Dagre를 사용한 자동 레이아웃 계산
 */
export function getLayoutedElements(
  nodes: Node<WorkflowNodeData>[],
  edges: Edge[],
  direction: 'TB' | 'LR' = 'TB'
): { nodes: Node<WorkflowNodeData>[]; edges: Edge[] } {
  const dagreGraph = new dagre.graphlib.Graph()
  dagreGraph.setDefaultEdgeLabel(() => ({}))

  const nodeWidth = 250
  const nodeHeight = 100

  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: 50,
    ranksep: 80,
    marginx: 20,
    marginy: 20,
  })

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight })
  })

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target)
  })

  dagre.layout(dagreGraph)

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id)
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - nodeWidth / 2,
        y: nodeWithPosition.y - nodeHeight / 2,
      },
    }
  })

  return { nodes: layoutedNodes, edges }
}

/**
 * 워크플로우의 방향 결정 (단계 수에 따라)
 */
export function getOptimalDirection(stepCount: number): 'TB' | 'LR' {
  // 5개 이하: 세로(TB), 6개 이상: 가로(LR)
  return stepCount <= 5 ? 'TB' : 'LR'
}

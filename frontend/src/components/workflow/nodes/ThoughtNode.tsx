import { memo } from 'react'
import { Handle, Position } from 'reactflow'
import { Brain } from 'lucide-react'
import type { WorkflowNodeData } from '../WorkflowConverter'

interface ThoughtNodeProps {
  data: WorkflowNodeData
  selected?: boolean
}

function ThoughtNode({ data, selected }: ThoughtNodeProps) {
  const { step, index } = data

  return (
    <div
      className={`
        px-4 py-3 rounded-lg border-2 bg-surface-secondary
        min-w-[220px] max-w-[250px]
        transition-all duration-200
        ${selected ? 'border-accent-primary shadow-lg' : 'border-border'}
      `}
    >
      <Handle type="target" position={Position.Top} className="!bg-accent-primary" />

      <div className="flex items-start gap-2 mb-2">
        <Brain size={16} className="text-purple-500 mt-0.5 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-xs font-semibold text-content-secondary mb-1">Thought #{index + 1}</div>
          <div className="text-sm text-content-primary line-clamp-3">{step.content || 'Thinking...'}</div>
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-accent-primary" />
    </div>
  )
}

export default memo(ThoughtNode)

import { memo } from 'react'
import { Handle, Position } from 'reactflow'
import { Wrench } from 'lucide-react'
import type { WorkflowNodeData } from '../WorkflowConverter'

interface ToolCallNodeProps {
  data: WorkflowNodeData
  selected?: boolean
}

function ToolCallNode({ data, selected }: ToolCallNodeProps) {
  const { step, index } = data

  // input을 간단하게 표시
  const inputPreview =
    step.input && typeof step.input === 'object'
      ? JSON.stringify(step.input, null, 2).slice(0, 100)
      : String(step.input || '').slice(0, 100)

  return (
    <div
      className={`
        px-4 py-3 rounded-lg border-2 bg-surface-secondary
        min-w-[220px] max-w-[250px]
        transition-all duration-200
        ${selected ? 'border-accent-primary shadow-lg' : 'border-accent-blue'}
      `}
    >
      <Handle type="target" position={Position.Top} className="!bg-accent-blue" />

      <div className="flex items-start gap-2 mb-2">
        <Wrench size={16} className="text-accent-blue mt-0.5 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-xs font-semibold text-accent-blue mb-1">Tool Call #{index + 1}</div>
          <div className="text-sm font-bold text-content-primary mb-1">{step.tool || 'Unknown Tool'}</div>
          {inputPreview && (
            <div className="text-xs text-content-muted font-mono bg-surface-tertiary px-2 py-1 rounded overflow-hidden text-ellipsis">
              {inputPreview}
              {inputPreview.length >= 100 && '...'}
            </div>
          )}
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-accent-blue" />
    </div>
  )
}

export default memo(ToolCallNode)

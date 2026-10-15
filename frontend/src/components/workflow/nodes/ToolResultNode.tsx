import { memo } from 'react'
import { Handle, Position } from 'reactflow'
import { CheckCircle, XCircle } from 'lucide-react'
import type { WorkflowNodeData } from '../WorkflowConverter'

interface ToolResultNodeProps {
  data: WorkflowNodeData
  selected?: boolean
}

function ToolResultNode({ data, selected }: ToolResultNodeProps) {
  const { step, index } = data

  const hasOutput = step.output !== undefined && step.output !== null && step.output !== ''
  const isSuccess = hasOutput

  // output을 간단하게 표시
  const outputPreview = step.output ? String(step.output).slice(0, 120) : 'No output'

  return (
    <div
      className={`
        px-4 py-3 rounded-lg border-2 bg-surface-secondary
        min-w-[220px] max-w-[250px]
        transition-all duration-200
        ${
          selected
            ? 'border-accent-primary shadow-lg'
            : isSuccess
              ? 'border-accent-green'
              : 'border-accent-orange'
        }
      `}
    >
      <Handle
        type="target"
        position={Position.Top}
        className={isSuccess ? '!bg-accent-green' : '!bg-accent-orange'}
      />

      <div className="flex items-start gap-2 mb-2">
        {isSuccess ? (
          <CheckCircle size={16} className="text-accent-green mt-0.5 flex-shrink-0" />
        ) : (
          <XCircle size={16} className="text-accent-orange mt-0.5 flex-shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div
            className={`text-xs font-semibold mb-1 ${isSuccess ? 'text-accent-green' : 'text-accent-orange'}`}
          >
            Result #{index + 1}
          </div>
          <div className="text-xs text-content-secondary font-mono bg-surface-tertiary px-2 py-1 rounded overflow-hidden line-clamp-3">
            {outputPreview}
            {outputPreview.length >= 120 && '...'}
          </div>
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className={isSuccess ? '!bg-accent-green' : '!bg-accent-orange'}
      />
    </div>
  )
}

export default memo(ToolResultNode)

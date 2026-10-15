import { Wrench, CheckCircle, Brain, Eye } from 'lucide-react'
import type { AgentStepData } from '../../types/chat'

export default function ToolCallCard({ step }: { step: AgentStepData }) {
  const isThought = step.type === 'thought'
  const isResult = step.type === 'tool_result'

  return (
    <div className="bg-surface-secondary rounded-lg px-3 py-2 text-xs border border-border">
      <div className="flex items-center gap-1.5 mb-1">
        {isThought ? (
          <Brain size={11} className="text-accent-purple" />
        ) : isResult ? (
          <CheckCircle size={11} className="text-accent-green" />
        ) : (
          <Wrench size={11} className="text-accent-primary" />
        )}
        <span
          className={`font-medium capitalize ${
            isThought ? 'text-accent-purple' : isResult ? 'text-accent-green' : 'text-accent-primary'
          }`}
        >
          {step.tool || step.type}
        </span>
      </div>
      {step.input != null && (
        <p className="text-content-secondary truncate font-mono">
          {JSON.stringify(step.input)}
        </p>
      )}
      {step.content && !step.input && (
        <p className="text-content-primary line-clamp-2">{step.content}</p>
      )}
      {step.output && (
        <p className="text-content-primary line-clamp-2 mt-1">{step.output}</p>
      )}
    </div>
  )
}

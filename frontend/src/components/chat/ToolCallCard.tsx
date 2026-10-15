import { Wrench, CheckCircle, Brain, Eye } from 'lucide-react'
import type { AgentStepData } from '../../types/chat'

export default function ToolCallCard({ step }: { step: AgentStepData }) {
  const isThought = step.type === 'thought'
  const isResult = step.type === 'tool_result'

  return (
    <div className="bg-slate-900/60 rounded-lg px-3 py-2 text-xs border border-slate-600/50">
      <div className="flex items-center gap-1.5 mb-1">
        {isThought ? (
          <Brain size={11} className="text-purple-400" />
        ) : isResult ? (
          <CheckCircle size={11} className="text-green-400" />
        ) : (
          <Wrench size={11} className="text-blue-400" />
        )}
        <span
          className={`font-medium capitalize ${
            isThought ? 'text-purple-400' : isResult ? 'text-green-400' : 'text-blue-400'
          }`}
        >
          {step.tool || step.type}
        </span>
      </div>
      {step.input != null && (
        <p className="text-slate-500 truncate font-mono">
          {JSON.stringify(step.input)}
        </p>
      )}
      {step.content && !step.input && (
        <p className="text-slate-300 line-clamp-2">{step.content}</p>
      )}
      {step.output && (
        <p className="text-slate-300 line-clamp-2 mt-1">{step.output}</p>
      )}
    </div>
  )
}

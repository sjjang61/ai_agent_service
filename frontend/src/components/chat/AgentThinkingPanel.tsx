import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import type { AgentStep } from '../../types/agent'
import StepProgressItem from './StepProgressItem'

export default function AgentThinkingPanel({ steps }: { steps: AgentStep[] }) {
  const [collapsed, setCollapsed] = useState(false)

  const lastStep = steps[steps.length - 1]
  const lastNarration = [...steps]
    .reverse()
    .find((s) => s.type === 'tool_call' && s.tool === 'narrate')?.input as { message?: string } | undefined
  const isActive = (step: AgentStep) => step === lastStep

  return (
    <div className="mx-4 mb-2 bg-slate-800/80 border border-slate-700 rounded-xl overflow-hidden">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-700/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
          <span className="font-medium">
            {typeof lastNarration?.message === 'string' ? lastNarration.message : 'Agent 작업 중...'} ({steps.length} steps)
          </span>
        </div>
        {collapsed ? <ChevronDown size={15} /> : <ChevronUp size={15} />}
      </button>

      {!collapsed && (
        <div className="px-3 pb-3 space-y-1 max-h-52 overflow-y-auto">
          {steps.map((step) => (
            <StepProgressItem
              key={step.id}
              step={step}
              isActive={isActive(step) && step.type === 'tool_call'}
            />
          ))}
        </div>
      )}
    </div>
  )
}

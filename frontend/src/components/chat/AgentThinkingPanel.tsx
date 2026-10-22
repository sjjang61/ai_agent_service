import { useState } from 'react'
import { ChevronDown, ChevronUp, HelpCircle } from 'lucide-react'
import type { AgentStep } from '../../types/agent'
import StepProgressItem from './StepProgressItem'
import { findPendingCall, statusText } from './pendingStep'

export default function AgentThinkingPanel({ steps }: { steps: AgentStep[] }) {
  const [collapsed, setCollapsed] = useState(false)

  const pendingCall = findPendingCall(steps) // 결과를 기다리는 가장 안쪽 도구 호출
  const lastNarration = [...steps]
    .reverse()
    .find((s) => s.type === 'tool_call' && s.tool === 'narrate')?.input as { message?: string } | undefined
  const isActive = (step: AgentStep) => step === pendingCall

  return (
    <div className="mx-4 mb-2 max-w-[800px] lg:mx-auto">
      <div className="bg-surface-secondary border border-border rounded-[var(--radius-lg)] overflow-hidden">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-between px-4 py-3 text-sm hover:bg-surface-hover transition-colors bg-surface-tertiary border-b border-border"
        >
          <div className="flex items-center gap-2.5">
            <HelpCircle size={16} className="text-accent-yellow" />
            <span className="font-medium text-content-secondary">
              {typeof lastNarration?.message === 'string' ? lastNarration.message : statusText(steps)} ({steps.length} steps)
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-accent-primary animate-pulse-slow" />
            {collapsed ? <ChevronDown size={15} className="text-content-muted" /> : <ChevronUp size={15} className="text-content-muted" />}
          </div>
        </button>

        {!collapsed && (
          <div className="px-4 py-3 space-y-2 max-h-52 overflow-y-auto">
            {steps.map((step) => (
              <StepProgressItem
                key={step.id}
                step={step}
                isActive={isActive(step)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

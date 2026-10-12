import { Brain, Wrench, CheckCircle2, Code2, FileText, Globe, Search, Terminal, ChevronRight, Loader2 } from 'lucide-react'
import { useAgentStore } from '../../store/agentStore'
import type { SelectedStepDetail } from '../../types/agent'

const TOOL_LABELS: Record<string, string> = {
  code_executor: '코드 실행',
  file_manager: '파일 관리',
  shell_executor: '쉘 실행',
  web_search: '웹 검색',
  web_crawler: '웹 크롤링',
}

function StepIcon({ type, tool, isActive }: { type: string; tool?: string; isActive?: boolean }) {
  if (isActive) return <Loader2 size={13} className="text-blue-400 animate-spin flex-shrink-0" />
  if (type === 'thought') return <Brain size={13} className="text-purple-400 flex-shrink-0" />
  if (type === 'tool_result') return <CheckCircle2 size={13} className="text-green-400 flex-shrink-0" />
  switch (tool) {
    case 'code_executor': return <Code2 size={13} className="text-amber-400 flex-shrink-0" />
    case 'file_manager': return <FileText size={13} className="text-cyan-400 flex-shrink-0" />
    case 'shell_executor': return <Terminal size={13} className="text-green-400 flex-shrink-0" />
    case 'web_search': return <Search size={13} className="text-blue-400 flex-shrink-0" />
    case 'web_crawler': return <Globe size={13} className="text-blue-400 flex-shrink-0" />
    default: return <Wrench size={13} className="text-blue-400 flex-shrink-0" />
  }
}

function getLabel(type: string, tool?: string) {
  if (type === 'thought') return '분석'
  if (type === 'tool_result') return `${TOOL_LABELS[tool ?? ''] ?? tool ?? '도구'} 완료`
  return TOOL_LABELS[tool ?? ''] ?? tool ?? '실행 중'
}

function getBadgeColor(type: string) {
  if (type === 'thought') return 'bg-purple-500/20 text-purple-300 border-purple-500/30'
  if (type === 'tool_result') return 'bg-green-500/20 text-green-300 border-green-500/30'
  return 'bg-blue-500/20 text-blue-300 border-blue-500/30'
}

interface Props {
  step: SelectedStepDetail
  isActive?: boolean
}

export default function StepProgressItem({ step, isActive = false }: Props) {
  const { selectedStep, setSelectedStep } = useAgentStore()
  const isSelected = selectedStep?.id === step.id

  const handleClick = () => {
    setSelectedStep(isSelected ? null : step)
  }

  return (
    <button
      onClick={handleClick}
      className={`
        w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs transition-colors text-left
        ${isSelected
          ? 'bg-slate-600/60 border border-slate-500/60'
          : 'bg-slate-800/60 border border-slate-700/40 hover:bg-slate-700/50 hover:border-slate-600/60'
        }
      `}
    >
      <StepIcon type={step.type} tool={step.tool} isActive={isActive} />
      <span className={`font-medium ${getBadgeColor(step.type)} px-1.5 py-0.5 rounded border text-[10px] flex-shrink-0`}>
        {getLabel(step.type, step.tool)}
      </span>
      <span className="text-slate-400 truncate flex-1 min-w-0">
        {step.content
          ? step.content.slice(0, 60)
          : step.input
          ? JSON.stringify(step.input).slice(0, 60)
          : step.output?.slice(0, 60) ?? ''}
      </span>
      <ChevronRight size={12} className={`flex-shrink-0 transition-transform ${isSelected ? 'rotate-90 text-slate-300' : 'text-slate-600'}`} />
    </button>
  )
}

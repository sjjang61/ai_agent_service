import { Brain, Wrench, CheckCircle2, Code2, FileText, Globe, Search, Terminal, ChevronRight, Loader2, Image as ImageIcon, Link2, LayoutDashboard, Bot, Plug, ListChecks, Megaphone, MessageCircleQuestion, AppWindow } from 'lucide-react'
import { useAgentStore } from '../../store/agentStore'
import type { SelectedStepDetail } from '../../types/agent'

const TOOL_LABELS: Record<string, string> = {
  code_executor: '코드 실행',
  file_manager: '파일 관리',
  shell_executor: '쉘 실행',
  web_search: '웹 검색',
  web_crawler: '웹 크롤링',
  read_file: '파일 읽기',
  write_file: '파일 쓰기',
  edit_file: '파일 수정',
  grep_file: '파일 검색',
  delete_file: '파일 삭제',
  download_file: '파일 다운로드',
  publish_file: '링크 발행',
  exec_command: '명령 실행',
  read_image: '이미지 분석',
  create_widget: '위젯 생성',
  load_skill: '스킬 불러오기',
  register_skill: '스킬 설치',
  call_sub_agent: '서브에이전트',
  load_mcp_tool: 'MCP 도구 확인',
  call_mcp_tool: 'MCP 호출',
  run_mcp_code: 'MCP 코드 실행',
  todo: '작업 계획',
  narrate: '진행 안내',
  form_ask_user: '사용자 질문',
  cli_browser_agent: '브라우저 작업',
}

function StepIcon({ type, tool, isActive }: { type: string; tool?: string; isActive?: boolean }) {
  if (isActive) return <Loader2 size={13} className="text-blue-400 animate-spin flex-shrink-0" />
  if (type === 'thought') return <Brain size={13} className="text-purple-400 flex-shrink-0" />
  if (type === 'tool_result') return <CheckCircle2 size={13} className="text-green-400 flex-shrink-0" />
  switch (tool) {
    case 'code_executor': return <Code2 size={13} className="text-amber-400 flex-shrink-0" />
    case 'file_manager': return <FileText size={13} className="text-cyan-400 flex-shrink-0" />
    case 'shell_executor': return <Terminal size={13} className="text-green-400 flex-shrink-0" />
    case 'read_file': case 'write_file': case 'edit_file': case 'grep_file': case 'delete_file': case 'download_file':
      return <FileText size={13} className="text-cyan-400 flex-shrink-0" />
    case 'exec_command': return <Terminal size={13} className="text-green-400 flex-shrink-0" />
    case 'publish_file': return <Link2 size={13} className="text-cyan-400 flex-shrink-0" />
    case 'todo': return <ListChecks size={13} className="text-green-400 flex-shrink-0" />
    case 'narrate': return <Megaphone size={13} className="text-purple-400 flex-shrink-0" />
    case 'form_ask_user': return <MessageCircleQuestion size={13} className="text-blue-400 flex-shrink-0" />
    case 'cli_browser_agent': return <AppWindow size={13} className="text-amber-400 flex-shrink-0" />
    case 'create_widget': return <LayoutDashboard size={13} className="text-purple-400 flex-shrink-0" />
    case 'call_sub_agent': return <Bot size={13} className="text-amber-400 flex-shrink-0" />
    case 'load_mcp_tool': case 'call_mcp_tool': return <Plug size={13} className="text-blue-400 flex-shrink-0" />
    case 'run_mcp_code': return <Code2 size={13} className="text-green-400 flex-shrink-0" />
    case 'read_image': return <ImageIcon size={13} className="text-purple-400 flex-shrink-0" />
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
        {step.tool === 'narrate' && step.type === 'tool_call' && typeof (step.input as { message?: string } | undefined)?.message === 'string'
          ? (step.input as { message: string }).message.slice(0, 120)
          : step.content
          ? step.content.slice(0, 60)
          : step.input
          ? JSON.stringify(step.input).slice(0, 60)
          : step.output?.slice(0, 60) ?? ''}
      </span>
      <ChevronRight size={12} className={`flex-shrink-0 transition-transform ${isSelected ? 'rotate-90 text-slate-300' : 'text-slate-600'}`} />
    </button>
  )
}

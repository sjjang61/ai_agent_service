import {
  X, Brain, Code2, FileText, Globe, Search, Wrench, CheckCircle2, File, Terminal
} from 'lucide-react'
import { useAgentStore } from '../../store/agentStore'
import ArtifactsPanel from './ArtifactsPanel'
import type { SelectedStepDetail } from '../../types/agent'

// ─── 스텝 상세 섹션 ────────────────────────────────────────────────────────────

function CodeBlock({ content, lang = '' }: { content: string; lang?: string }) {
  return (
    <pre className={`bg-slate-950 rounded-lg p-3 text-xs font-mono overflow-auto max-h-64 text-slate-300 whitespace-pre-wrap break-words border border-slate-700/50 ${lang}`}>
      {content}
    </pre>
  )
}

function StepDetailContent({ step }: { step: SelectedStepDetail }) {
  const isSandboxTool = step.tool === 'code_executor' || step.tool === 'file_manager'

  if (step.type === 'thought') {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-purple-400 text-xs font-medium">
          <Brain size={13} /> <span>에이전트 분석</span>
        </div>
        <CodeBlock content={step.content ?? '(내용 없음)'} />
      </div>
    )
  }

  if (step.type === 'tool_call') {
    const input = step.input as Record<string, unknown> | undefined
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-blue-400 text-xs font-medium">
          <ToolIcon tool={step.tool} />
          <span>{step.tool}</span>
          <span className="text-slate-500 font-normal">호출</span>
        </div>
        {input && (
          <>
            {step.tool === 'code_executor' && typeof input.code === 'string' && (
              <div className="space-y-1">
                {input.filename && (
                  <p className="text-xs text-slate-400 font-mono">파일: {String(input.filename)}</p>
                )}
                <p className="text-[10px] text-slate-500 uppercase tracking-wide">코드</p>
                <CodeBlock content={input.code} lang="python" />
              </div>
            )}
            {step.tool === 'file_manager' && (
              <div className="space-y-1">
                <p className="text-xs text-slate-400">
                  작업: <span className="text-cyan-400 font-medium">{String(input.operation ?? '')}</span>
                  {input.path && <span className="ml-2 font-mono text-slate-300">{String(input.path)}</span>}
                </p>
                {input.content && (
                  <>
                    <p className="text-[10px] text-slate-500 uppercase tracking-wide">내용</p>
                    <CodeBlock content={String(input.content)} />
                  </>
                )}
              </div>
            )}
            {!isSandboxTool && (
              <>
                <p className="text-[10px] text-slate-500 uppercase tracking-wide">입력</p>
                <CodeBlock content={JSON.stringify(input, null, 2)} />
              </>
            )}
          </>
        )}
      </div>
    )
  }

  // tool_result
  const output = step.output ?? ''
  const savedFileMatch = output.match(/\[saved: ([^\]]+)\]/)
  const stdoutMatch = output.match(/STDOUT:\n([\s\S]*?)(?=STDERR:|Exit code:|$)/)
  const stderrMatch = output.match(/STDERR:\n([\s\S]*?)(?=Exit code:|$)/)
  const exitMatch = output.match(/Exit code: (\d+)/)

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-green-400 text-xs font-medium">
        <CheckCircle2 size={13} />
        <ToolIcon tool={step.tool} />
        <span>{step.tool}</span>
        <span className="text-slate-500 font-normal">결과</span>
      </div>

      {(step.tool === 'code_executor' || step.tool === 'shell_executor') && (savedFileMatch || stdoutMatch || exitMatch) ? (
        <div className="space-y-2">
          {savedFileMatch && (
            <p className="text-xs text-cyan-400 font-mono flex items-center gap-1.5">
              <File size={11} /> {savedFileMatch[1]}
            </p>
          )}
          {stdoutMatch?.[1]?.trim() && (
            <div>
              <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-1">출력</p>
              <CodeBlock content={stdoutMatch[1].trim()} />
            </div>
          )}
          {stderrMatch?.[1]?.trim() && (
            <div>
              <p className="text-[10px] text-red-400 uppercase tracking-wide mb-1">오류</p>
              <CodeBlock content={stderrMatch[1].trim()} />
            </div>
          )}
          {exitMatch && (
            <p className="text-[10px] text-slate-500">
              Exit code: <span className={exitMatch[1] === '0' ? 'text-green-400' : 'text-red-400'}>{exitMatch[1]}</span>
            </p>
          )}
        </div>
      ) : (
        <CodeBlock content={output || '(결과 없음)'} />
      )}
    </div>
  )
}

function ToolIcon({ tool }: { tool?: string }) {
  switch (tool) {
    case 'code_executor': return <Code2 size={13} className="text-amber-400" />
    case 'file_manager': return <FileText size={13} className="text-cyan-400" />
    case 'shell_executor': case 'exec_command': return <Terminal size={13} className="text-green-400" />
    case 'read_file': case 'write_file': case 'edit_file': case 'grep_file': case 'delete_file': case 'download_file': case 'publish_file':
      return <FileText size={13} className="text-cyan-400" />
    case 'web_search': return <Search size={13} className="text-blue-400" />
    case 'web_crawler': return <Globe size={13} className="text-blue-400" />
    default: return <Wrench size={13} className="text-blue-400" />
  }
}

// ─── 메인 패널 ────────────────────────────────────────────────────────────────

export default function SandboxDetailPanel() {
  const { selectedStep, setSelectedStep, workspaceRefreshTick } = useAgentStore()

  if (!selectedStep) return null

  return (
    <div className="w-[400px] flex-shrink-0 bg-slate-850 border-l border-slate-700/60 flex flex-col h-screen overflow-hidden"
      style={{ backgroundColor: '#0f172a' }}
    >
      {/* 헤더 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/50 bg-slate-900/60">
        <div className="flex items-center gap-2 text-sm font-medium text-slate-200">
          <ToolIcon tool={selectedStep.tool} />
          <span>상세 보기</span>
        </div>
        <button
          onClick={() => setSelectedStep(null)}
          className="text-slate-500 hover:text-slate-200 transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      {/* 콘텐츠 */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-2">
        <StepDetailContent step={selectedStep} />
        <div className="border-t border-slate-700/50 pt-3 mt-3">
          <ArtifactsPanel compact refreshTick={workspaceRefreshTick} />
        </div>
      </div>
    </div>
  )
}

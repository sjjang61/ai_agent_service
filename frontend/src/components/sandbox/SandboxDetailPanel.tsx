import { useEffect, useState } from 'react'
import {
  X, Brain, Code2, FileText, Globe, Search, Wrench, CheckCircle2,
  ChevronDown, ChevronRight, File, FolderOpen, RefreshCw, Terminal
} from 'lucide-react'
import { useAgentStore } from '../../store/agentStore'
import { sandboxApi } from '../../api/sandbox'
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
    case 'shell_executor': return <Terminal size={13} className="text-green-400" />
    case 'web_search': return <Search size={13} className="text-blue-400" />
    case 'web_crawler': return <Globe size={13} className="text-blue-400" />
    default: return <Wrench size={13} className="text-blue-400" />
  }
}

// ─── 워크스페이스 파일 트리 ──────────────────────────────────────────────────────

interface FileViewerProps {
  path: string
  onClose: () => void
}

function FileViewer({ path, onClose }: FileViewerProps) {
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    sandboxApi.getFileContent(path)
      .then((r) => setContent(r.data.content))
      .catch(() => setContent('파일을 읽을 수 없습니다.'))
      .finally(() => setLoading(false))
  }, [path])

  return (
    <div className="mt-2 space-y-1.5">
      <div className="flex items-center justify-between">
        <p className="text-[10px] text-slate-400 font-mono truncate">{path}</p>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-300 text-xs">닫기</button>
      </div>
      {loading
        ? <p className="text-xs text-slate-500">로딩 중...</p>
        : <CodeBlock content={content ?? ''} />
      }
    </div>
  )
}

function WorkspaceTree({ refreshTick }: { refreshTick: number }) {
  const [files, setFiles] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [openFile, setOpenFile] = useState<string | null>(null)
  const [collapsed, setCollapsed] = useState(false)

  const load = () => {
    setLoading(true)
    sandboxApi.getWorkspaceTree()
      .then((r) => setFiles(r.data.files))
      .catch(() => setFiles([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [refreshTick])

  if (files.length === 0 && !loading) return null

  return (
    <div className="border-t border-slate-700/50 pt-3 mt-3">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors w-full mb-2"
      >
        {collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
        <FolderOpen size={12} />
        <span className="font-medium">워크스페이스 파일 ({files.length})</span>
        <button
          onClick={(e) => { e.stopPropagation(); load() }}
          className="ml-auto text-slate-600 hover:text-slate-400"
        >
          <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
        </button>
      </button>

      {!collapsed && (
        <div className="space-y-0.5">
          {files.map((f) => (
            <div key={f}>
              <button
                onClick={() => setOpenFile(openFile === f ? null : f)}
                className={`w-full flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-colors text-left ${
                  openFile === f ? 'bg-slate-700/60 text-slate-200' : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-300'
                }`}
              >
                <File size={11} className="flex-shrink-0 text-slate-500" />
                <span className="font-mono truncate">{f}</span>
              </button>
              {openFile === f && (
                <FileViewer path={f} onClose={() => setOpenFile(null)} />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
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
        <WorkspaceTree refreshTick={workspaceRefreshTick} />
      </div>
    </div>
  )
}

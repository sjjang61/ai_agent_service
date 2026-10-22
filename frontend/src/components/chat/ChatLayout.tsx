import IconBar from '../layout/IconBar'
import Sidebar from './Sidebar'
import MessageList from './MessageList'
import InputBar from './InputBar'
import StepsPanel from './StepsPanel'
import { buildTaskItems } from './taskItems'
import SandboxDetailPanel from '../sandbox/SandboxDetailPanel'
import ArtifactsPanel from '../sandbox/ArtifactsPanel'
import WelcomeScreen from './WelcomeScreen'
import RightPanel from '../layout/RightPanel'
import DocumentsPanel from '../documents/DocumentsPanel'
import { useDocuments } from '../../hooks/useDocuments'
import { useEffect, useRef } from 'react'
import { FileText, FolderOpen, ListChecks, Loader2 } from 'lucide-react'
import type { AgentStep } from '../../types/agent'
import { useChatStore } from '../../store/chatStore'
import { useAgentStore } from '../../store/agentStore'

export default function ChatLayout() {
  const { currentConversationId, conversations } = useChatStore()
  const currentConversation = conversations.find((c) => c.id === currentConversationId)
  const { isRunning, currentSteps, stepsOwner, selectedStep, rightPanel, togglePanel, closePanel, workspaceRefreshTick } = useAgentStore()
  const messages = useChatStore((s) => (currentConversationId ? s.messages[currentConversationId] : undefined))
  // 작업 진행 패널에 보여 줄 단계: 이 대화의 실시간 단계, 없으면 마지막 응답에 저장된 단계
  const liveSteps = stepsOwner === currentConversationId ? currentSteps : []
  const lastAssistant = [...(messages ?? [])].reverse().find((m) => m.role === 'assistant')
  const savedSteps: AgentStep[] = (lastAssistant?.agent_steps ?? []).map((s, i) => ({
    id: `saved-${lastAssistant?.id}-${i}`,
    type: s.type as AgentStep['type'],
    tool: s.tool,
    content: s.content,
    input: s.input,
    output: s.output,
    timestamp: lastAssistant?.created_at ?? '',
  }))
  const panelSteps = liveSteps.length > 0 ? liveSteps : savedSteps
  const taskCount = buildTaskItems(panelSteps).length
  const running = isRunning && stepsOwner === currentConversationId

  // 실행이 시작돼 첫 단계가 생기면 우측에 작업 진행 패널을 자동으로 연다. 사용자가 닫으면 그 실행 동안은 다시 열지 않고,
  // 다른 패널(문서·Artifacts)을 보고 있으면 건드리지 않는다.
  const autoOpened = useRef(false)
  useEffect(() => {
    if (!running) {
      autoOpened.current = false
      return
    }
    if (liveSteps.length > 0 && !autoOpened.current) {
      autoOpened.current = true
      if (useAgentStore.getState().rightPanel === null) useAgentStore.getState().togglePanel('steps')
    }
  }, [running, liveSteps.length])
  const { data: documents = [] } = useDocuments(currentConversationId)
  const docsProcessing = documents.some((d) => d.status === 'processing')
  const headerBtn = (active: boolean) =>
    `flex items-center gap-1.5 px-2.5 py-1.5 rounded-[var(--radius-md)] text-xs border transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${
      active
        ? 'bg-accent-primary border-accent-primary text-white'
        : 'bg-surface-secondary border-border text-content-secondary hover:text-content-primary hover:bg-surface-hover'
    }`

  return (
    <div className="flex h-screen bg-surface-primary overflow-hidden">
      {/* Left Icon Bar */}
      <IconBar />

      {/* Sidebar */}
      <Sidebar />

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 relative bg-surface-primary">
        {/* 커스텀 에이전트로 시작한 대화: 어떤 에이전트의 어떤 버전인지 표시 */}
        {currentConversation?.agent_name && (
          <div className="absolute top-3 left-4 z-10 flex items-center gap-1.5 px-2.5 py-1.5 rounded-[var(--radius-md)] text-xs border bg-surface-secondary border-border text-content-secondary">
            <span>{currentConversation.agent_icon}</span>
            <span className="font-medium text-content-primary">{currentConversation.agent_name}</span>
            {currentConversation.agent_version != null && <span className="text-content-tertiary">v{currentConversation.agent_version}</span>}
          </div>
        )}

        {/* 우측 패널 토글: 작업 진행 · 문서(RAG) · Artifacts */}
        <div className="absolute top-3 right-4 z-10 flex items-center gap-2">
          <button
            onClick={() => togglePanel('steps')}
            disabled={!currentConversationId}
            title="에이전트의 작업 진행 (분석·도구 호출)"
            aria-pressed={rightPanel === 'steps'}
            className={headerBtn(rightPanel === 'steps')}
          >
            <ListChecks size={13} />
            진행
            {running ? (
              <Loader2 size={11} className="animate-spin" aria-label="진행 중" />
            ) : taskCount > 0 ? (
              <span className={`min-w-[16px] px-1 rounded-full text-[10px] font-semibold text-center ${rightPanel === 'steps' ? 'bg-white/25' : 'bg-surface-tertiary text-content-secondary'}`}>
                {taskCount}
              </span>
            ) : null}
          </button>
          <button
            onClick={() => togglePanel('documents')}
            disabled={!currentConversationId}
            title={currentConversationId ? '이 대화의 RAG 문서 (업로드한 문서를 검색해 답변에 활용)' : '대화를 선택하면 문서를 올릴 수 있습니다'}
            aria-pressed={rightPanel === 'documents'}
            className={headerBtn(rightPanel === 'documents')}
          >
            <FileText size={13} />
            문서
            {docsProcessing ? (
              <Loader2 size={11} className="animate-spin" aria-label="처리 중" />
            ) : documents.length > 0 ? (
              <span className={`min-w-[16px] px-1 rounded-full text-[10px] font-semibold text-center ${rightPanel === 'documents' ? 'bg-white/25' : 'bg-surface-tertiary text-content-secondary'}`}>
                {documents.length}
              </span>
            ) : null}
          </button>
          <button
            onClick={() => togglePanel('artifacts')}
            title="Artifacts (Sandbox Files)"
            aria-pressed={rightPanel === 'artifacts'}
            className={headerBtn(rightPanel === 'artifacts')}
          >
            <FolderOpen size={13} />
            Artifacts
          </button>
        </div>

        {currentConversationId ? (
          <>
            <MessageList conversationId={currentConversationId} />
            <InputBar conversationId={currentConversationId} />
          </>
        ) : (
          <WelcomeScreen />
        )}
      </main>

      {/* Right Detail Panel - Step Details */}
      {selectedStep && <SandboxDetailPanel />}

      {/* Right Panels (단계 상세가 열려 있으면 그쪽이 우선) */}
      {!selectedStep && rightPanel === 'steps' && currentConversationId && (
        <RightPanel title="작업 진행" subtitle={running ? '에이전트가 작업하고 있습니다' : '마지막 작업의 진행 내역'} icon={<ListChecks size={15} />} onClose={closePanel}>
          <StepsPanel steps={panelSteps} running={running} />
        </RightPanel>
      )}
      {!selectedStep && rightPanel === 'artifacts' && (
        <RightPanel title="Sandbox Artifacts" icon={<FolderOpen size={15} />} onClose={closePanel}>
          <div className="px-4 py-4">
            <ArtifactsPanel compact refreshTick={workspaceRefreshTick} />
          </div>
        </RightPanel>
      )}
      {!selectedStep && rightPanel === 'documents' && currentConversationId && (
        <RightPanel title="문서 (RAG)" subtitle="이 대화에서 검색해 참고할 문서" icon={<FileText size={15} />} onClose={closePanel}>
          <DocumentsPanel conversationId={currentConversationId} />
        </RightPanel>
      )}
    </div>
  )
}

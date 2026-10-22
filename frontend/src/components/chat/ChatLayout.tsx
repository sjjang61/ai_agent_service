import IconBar from '../layout/IconBar'
import Sidebar from './Sidebar'
import MessageList from './MessageList'
import InputBar from './InputBar'
import AgentThinkingPanel from './AgentThinkingPanel'
import SandboxDetailPanel from '../sandbox/SandboxDetailPanel'
import ArtifactsPanel from '../sandbox/ArtifactsPanel'
import WelcomeScreen from './WelcomeScreen'
import { FolderOpen, X } from 'lucide-react'
import { useChatStore } from '../../store/chatStore'
import { useAgentStore } from '../../store/agentStore'

export default function ChatLayout() {
  const { currentConversationId, conversations } = useChatStore()
  const currentConversation = conversations.find((c) => c.id === currentConversationId)
  const { isRunning, currentSteps, selectedStep, artifactsOpen, toggleArtifacts, workspaceRefreshTick } = useAgentStore()

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

        {/* Artifacts Toggle Button */}
        <button
          onClick={() => toggleArtifacts()}
          title="Artifacts (Sandbox Files)"
          className={`absolute top-3 right-4 z-10 flex items-center gap-1.5 px-2.5 py-1.5 rounded-[var(--radius-md)] text-xs border transition-colors ${
            artifactsOpen
              ? 'bg-accent-primary border-accent-primary text-white'
              : 'bg-surface-secondary border-border text-content-secondary hover:text-content-primary hover:bg-surface-hover'
          }`}
        >
          <FolderOpen size={13} />
          Artifacts
        </button>

        {currentConversationId ? (
          <>
            <MessageList conversationId={currentConversationId} />
            {isRunning && currentSteps.length > 0 && (
              <AgentThinkingPanel steps={currentSteps} />
            )}
            <InputBar conversationId={currentConversationId} />
          </>
        ) : (
          <WelcomeScreen />
        )}
      </main>

      {/* Right Detail Panel - Step Details */}
      {selectedStep && <SandboxDetailPanel />}

      {/* Right Artifacts Panel */}
      {!selectedStep && artifactsOpen && (
        <div className="w-[420px] flex-shrink-0 border-l border-border flex flex-col h-screen overflow-hidden bg-surface-primary">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface-secondary">
            <span className="text-sm font-medium text-content-primary">Sandbox Artifacts</span>
            <button
              onClick={() => toggleArtifacts(false)}
              className="text-content-muted hover:text-content-primary transition-colors"
            >
              <X size={16} />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-4 py-4">
            <ArtifactsPanel compact refreshTick={workspaceRefreshTick} />
          </div>
        </div>
      )}
    </div>
  )
}

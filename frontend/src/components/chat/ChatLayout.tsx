import Sidebar from './Sidebar'
import MessageList from './MessageList'
import InputBar from './InputBar'
import AgentThinkingPanel from './AgentThinkingPanel'
import SandboxDetailPanel from '../sandbox/SandboxDetailPanel'
import ArtifactsPanel from '../sandbox/ArtifactsPanel'
import { FolderOpen, X } from 'lucide-react'
import { useChatStore } from '../../store/chatStore'
import { useAgentStore } from '../../store/agentStore'

export default function ChatLayout() {
  const { currentConversationId } = useChatStore()
  const { isRunning, currentSteps, selectedStep, artifactsOpen, toggleArtifacts, workspaceRefreshTick } = useAgentStore()

  return (
    <div className="flex h-screen bg-slate-900 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 relative">
        {/* 산출물(sandbox 파일) 보기 토글 */}
        <button
          onClick={() => toggleArtifacts()}
          title="산출물 (Sandbox 파일)"
          className={`absolute top-3 right-4 z-10 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border transition-colors ${
            artifactsOpen
              ? 'bg-blue-600 border-blue-500 text-white'
              : 'bg-slate-800/90 border-slate-700 text-slate-300 hover:text-white hover:bg-slate-700'
          }`}
        >
          <FolderOpen size={13} />
          산출물
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
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <h2 className="text-2xl font-bold text-white mb-2">AI Agent Platform</h2>
              <p className="text-slate-400">Start a new conversation from the sidebar</p>
            </div>
          </div>
        )}
      </div>
      {/* 우측 상세 패널 - step 선택 시 표시 */}
      {selectedStep && <SandboxDetailPanel />}
      {/* 우측 산출물 패널 - step 상세가 열려 있지 않을 때 표시 */}
      {!selectedStep && artifactsOpen && (
        <div className="w-[420px] flex-shrink-0 border-l border-slate-700/60 flex flex-col h-screen overflow-hidden bg-slate-900">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/50 bg-slate-900/60">
            <span className="text-sm font-medium text-slate-200">Sandbox 산출물</span>
            <button onClick={() => toggleArtifacts(false)} className="text-slate-500 hover:text-slate-200">
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

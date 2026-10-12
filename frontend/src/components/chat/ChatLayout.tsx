import Sidebar from './Sidebar'
import MessageList from './MessageList'
import InputBar from './InputBar'
import AgentThinkingPanel from './AgentThinkingPanel'
import SandboxDetailPanel from '../sandbox/SandboxDetailPanel'
import { useChatStore } from '../../store/chatStore'
import { useAgentStore } from '../../store/agentStore'

export default function ChatLayout() {
  const { currentConversationId } = useChatStore()
  const { isRunning, currentSteps, selectedStep } = useAgentStore()

  return (
    <div className="flex h-screen bg-slate-900 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
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
    </div>
  )
}

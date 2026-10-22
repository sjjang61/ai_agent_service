import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  PenSquare,
  Bot,
  Folder,
  MessageSquare,
  ChevronDown,
  RefreshCw,
  Search,
  Trash2,
  Settings,
  Sparkles,
  Box,
  Brain,
  LogOut,
  BarChart3,
  Wrench,
} from 'lucide-react'
import { useChatStore } from '../../store/chatStore'
import { chatApi } from '../../api/chat'
import { agentsApi } from '../../api/agents'
import type { CustomAgentSummary } from '../../types/customAgent'
import { useAuthStore } from '../../store/authStore'
import type { Conversation } from '../../types/chat'
import DocumentPanel from './DocumentPanel'

export default function Sidebar() {
  const {
    conversations,
    currentConversationId,
    addConversation,
    removeConversation,
    setCurrentConversation,
  } = useChatStore()
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleNewChat = async () => {
    const res = await chatApi.createConversation({ title: 'New Conversation' })
    addConversation(res.data as Conversation)
    navigate(`/chat/${res.data.id}`)
  }

  // My Agent: 발행된 커스텀 에이전트로 새 대화 시작
  const [agentsOpen, setAgentsOpen] = useState(false)
  const { data: agents = [] } = useQuery<CustomAgentSummary[]>({
    queryKey: ['agents'],
    queryFn: async () => (await agentsApi.list()).data,
    retry: false,
  })
  const published = agents.filter((a) => a.published_version !== null)

  const startAgentChat = async (agent: CustomAgentSummary) => {
    const res = await chatApi.createConversation({ title: 'New Conversation', agent_id: agent.id })
    addConversation(res.data as Conversation)
    navigate(`/chat/${res.data.id}`)
  }

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    await chatApi.deleteConversation(id)
    removeConversation(id)
    if (currentConversationId === id) navigate('/')
  }

  const handleSelect = (conv: Conversation) => {
    setCurrentConversation(conv.id)
    navigate(`/chat/${conv.id}`)
  }

  // Group conversations by date (simplified)
  const today = new Date().toDateString()
  const todayConversations = conversations.filter(
    (c) => new Date(c.created_at).toDateString() === today
  )
  const olderConversations = conversations.filter(
    (c) => new Date(c.created_at).toDateString() !== today
  )

  return (
    <aside className="w-[var(--sidebar-width)] bg-surface-secondary border-r border-border flex flex-col overflow-hidden flex-shrink-0">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2 text-[15px] font-semibold text-content-primary">
          Agent
          <ChevronDown size={16} className="text-content-secondary" />
        </div>
        <div className="flex gap-1">
          <button
            title="Refresh"
            className="w-7 h-7 rounded-[var(--radius-sm)] flex items-center justify-center
              text-content-secondary hover:text-content-primary hover:bg-surface-hover transition-colors"
          >
            <RefreshCw size={16} />
          </button>
          <button
            title="Search"
            className="w-7 h-7 rounded-[var(--radius-sm)] flex items-center justify-center
              text-content-secondary hover:text-content-primary hover:bg-surface-hover transition-colors"
          >
            <Search size={16} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-2">
        {/* New Chat */}
        <button
          onClick={handleNewChat}
          className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-[var(--radius-md)]
            text-content-primary hover:bg-surface-hover transition-colors text-left"
        >
          <PenSquare size={18} className="text-content-secondary" />
          <span className="text-sm">New Chat</span>
        </button>

        {/* My Agent: 커스텀 에이전트 */}
        <div>
          <button
            onClick={() => setAgentsOpen((o) => !o)}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-[var(--radius-md)]
              text-content-primary hover:bg-surface-hover transition-colors text-left"
            aria-expanded={agentsOpen}
          >
            <span className="text-base">🤖</span>
            <span className="text-sm flex-1">My Agent</span>
            <span className="bg-accent-primary text-white text-[11px] font-semibold px-1.5 py-0.5 rounded-full min-w-[20px] text-center">
              {published.length}
            </span>
            <ChevronDown size={14} className={`text-content-muted transition-transform ${agentsOpen ? 'rotate-180' : ''}`} />
          </button>
          {agentsOpen && (
            <div className="mt-0.5 mb-1 space-y-0.5">
              {published.map((a) => (
                <button
                  key={a.id}
                  onClick={() => startAgentChat(a)}
                  title={a.description || `${a.name}로 새 대화 시작`}
                  className="w-full flex items-center gap-2 pl-8 pr-3 py-1.5 rounded-[var(--radius-md)] text-left text-sm
                    text-content-secondary hover:bg-surface-hover hover:text-content-primary transition-colors"
                >
                  <span className="flex-shrink-0">{a.icon}</span>
                  <span className="truncate flex-1">{a.name}</span>
                  <span className="text-[10px] text-content-tertiary flex-shrink-0">v{a.published_version}</span>
                </button>
              ))}
              {published.length === 0 && (
                <p className="pl-8 pr-3 py-1 text-xs text-content-muted">발행된 에이전트가 없습니다</p>
              )}
              <button
                onClick={() => navigate('/agents')}
                className="w-full pl-8 pr-3 py-1.5 rounded-[var(--radius-md)] text-left text-xs text-accent-primary hover:bg-surface-hover transition-colors"
              >
                에이전트 만들기·관리
              </button>
            </div>
          )}
        </div>

        {/* Projects Section */}
        <div className="mt-4">
          <div className="px-3 py-2 text-xs font-medium text-content-tertiary uppercase tracking-wider">
            Conversations
          </div>

          {/* Today */}
          {todayConversations.length > 0 && (
            <div className="mb-2">
              <div className="px-3 py-1.5 text-xs text-content-tertiary">Today</div>
              {todayConversations.map((conv) => (
                <ConversationItem
                  key={conv.id}
                  conversation={conv}
                  isActive={currentConversationId === conv.id}
                  onClick={() => handleSelect(conv)}
                  onDelete={(e) => handleDelete(e, conv.id)}
                />
              ))}
            </div>
          )}

          {/* Older */}
          {olderConversations.length > 0 && (
            <div>
              <div className="px-3 py-1.5 text-xs text-content-tertiary">Earlier</div>
              {olderConversations.map((conv) => (
                <ConversationItem
                  key={conv.id}
                  conversation={conv}
                  isActive={currentConversationId === conv.id}
                  onClick={() => handleSelect(conv)}
                  onDelete={(e) => handleDelete(e, conv.id)}
                />
              ))}
            </div>
          )}

          {conversations.length === 0 && (
            <p className="text-content-muted text-xs text-center mt-6 px-3">
              No conversations yet. Start one!
            </p>
          )}
        </div>

        {/* RAG Documents Panel - only show when a conversation is selected */}
        {currentConversationId && <DocumentPanel conversationId={currentConversationId} />}
      </div>

      {/* Footer - Quick Links */}
      <div className="p-2 border-t border-border space-y-0.5">
        <button
          onClick={() => navigate('/tools')}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-[var(--radius-md)]
            text-content-secondary hover:text-content-primary hover:bg-surface-hover transition-colors text-left text-sm"
        >
          <Wrench size={15} />
          Tools
        </button>
        <button
          onClick={() => navigate('/mcp')}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-[var(--radius-md)]
            text-content-secondary hover:text-content-primary hover:bg-surface-hover transition-colors text-left text-sm"
        >
          <Settings size={15} />
          MCP Settings
        </button>
        <button
          onClick={() => navigate('/skills')}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-[var(--radius-md)]
            text-content-secondary hover:text-content-primary hover:bg-surface-hover transition-colors text-left text-sm"
        >
          <Sparkles size={15} />
          Skills
        </button>
        <button
          onClick={() => navigate('/memory')}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-[var(--radius-md)]
            text-content-secondary hover:text-content-primary hover:bg-surface-hover transition-colors text-left text-sm"
        >
          <Brain size={15} />
          Memory
        </button>
        <button
          onClick={() => navigate('/sandbox')}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-[var(--radius-md)]
            text-content-secondary hover:text-content-primary hover:bg-surface-hover transition-colors text-left text-sm"
        >
          <Box size={15} />
          Sandbox
        </button>
        <button
          onClick={() => navigate('/admin/usage')}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-[var(--radius-md)]
            text-content-secondary hover:text-content-primary hover:bg-surface-hover transition-colors text-left text-sm"
        >
          <BarChart3 size={15} />
          Token Usage
        </button>
        <div className="flex items-center justify-between px-3 py-2 mt-1">
          <span className="text-xs text-content-tertiary truncate">{user?.display_name}</span>
          <button
            onClick={() => {
              logout()
              navigate('/auth')
            }}
            className="text-content-muted hover:text-accent-red transition-colors"
            title="Logout"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </aside>
  )
}

interface ConversationItemProps {
  conversation: Conversation
  isActive: boolean
  onClick: () => void
  onDelete: (e: React.MouseEvent) => void
}

function ConversationItem({ conversation, isActive, onClick, onDelete }: ConversationItemProps) {
  return (
    <div
      onClick={onClick}
      className={`group flex items-center gap-2 px-3 py-2 rounded-[var(--radius-md)] cursor-pointer transition-colors ${
        isActive
          ? 'bg-surface-active text-content-primary'
          : 'text-content-secondary hover:bg-surface-hover hover:text-content-primary'
      }`}
    >
      {conversation.agent_icon ? (
        <span className="text-sm flex-shrink-0" title={`${conversation.agent_name} v${conversation.agent_version ?? ''}`}>{conversation.agent_icon}</span>
      ) : (
        <MessageSquare size={14} className="flex-shrink-0" />
      )}
      <span className="text-sm truncate flex-1">{conversation.title}</span>
      <button
        onClick={onDelete}
        className="opacity-0 group-hover:opacity-100 text-content-muted hover:text-accent-red transition-all flex-shrink-0"
      >
        <Trash2 size={12} />
      </button>
    </div>
  )
}

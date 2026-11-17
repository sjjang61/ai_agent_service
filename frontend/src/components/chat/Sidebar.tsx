import { useEffect, useState } from 'react'
import SearchDialog from './SearchDialog'
import { dayKey, parseServerDate } from '../../utils/time'
import { useLocation, useNavigate } from 'react-router-dom'
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
  Layers,
  Settings,
  Sparkles,
  Box,
  Brain,
  LogOut,
  BarChart3,
  Wrench,
  PanelLeftClose,
  PanelLeftOpen,
  Rocket,
  Store,
} from 'lucide-react'
import { useChatStore } from '../../store/chatStore'
import { useLayoutStore } from '../../store/layoutStore'
import { IconButton } from '../layout/IconButton'
import { chatApi } from '../../api/chat'
import { agentsApi } from '../../api/agents'
import type { CustomAgentSummary } from '../../types/customAgent'
import { appsApi, type DeployedApp } from '../../api/apps'
import { useAuthStore } from '../../store/authStore'
import type { Conversation } from '../../types/chat'

export default function Sidebar() {
  const collapsed = useLayoutStore((s) => s.sidebarCollapsed)
  const toggleSidebar = useLayoutStore((s) => s.toggleSidebar)
  const {
    conversations,
    currentConversationId,
    addConversation,
    removeConversation,
    setCurrentConversation,
  } = useChatStore()
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()

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

  // My Apps: 내가 배포한 웹앱 (누르면 My Apps 화면에서 실행)
  const [appsOpen, setAppsOpen] = useState(false)
  const { data: myApps = [] } = useQuery<DeployedApp[]>({
    queryKey: ['deployed-apps', 'runnable'],
    queryFn: async () => (await appsApi.listRunnable()).data,
    refetchInterval: 15000,
    retry: false,
  })
  const APP_DOT: Record<DeployedApp['status'], string> = { running: 'bg-accent-done', starting: 'bg-accent-primary animate-pulse', stopped: 'bg-content-muted', failed: 'bg-accent-red' }

  const startAgentChat = async (agent: CustomAgentSummary) => {
    const res = await chatApi.createConversation({ title: 'New Conversation', agent_id: agent.id })
    addConversation(res.data as Conversation)
    navigate(`/chat/${res.data.id}`)
  }

  // 대화 검색: 사이드바의 검색 버튼 또는 Ctrl/⌘+K
  const [searchOpen, setSearchOpen] = useState(false)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setSearchOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    if (!confirm('이 대화를 삭제할까요? 삭제한 대화는 복구할 수 없습니다.\n\n이 대화의 작업공간(sandbox) 파일도 함께 삭제됩니다. 보관할 산출물이 있다면 먼저 Artifacts 에서 Drive 에 저장하세요.')) return
    try {
      await chatApi.deleteConversation(id)
    } catch {
      alert('대화를 삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.')
      return
    }
    removeConversation(id)
    if (currentConversationId === id) navigate('/')
  }

  const handleSelect = (conv: Conversation) => {
    setCurrentConversation(conv.id)
    navigate(`/chat/${conv.id}`)
  }

  // Group conversations by date (simplified)
  const today = dayKey(new Date())
  const todayConversations = conversations.filter((c) => dayKey(parseServerDate(c.created_at)) === today)
  const olderConversations = conversations.filter((c) => dayKey(parseServerDate(c.created_at)) !== today)

  // 접힌 상태: 아이콘만 세로로 두고, 이름과 설명은 마우스를 올리거나 포커스하면 툴팁으로 보여 준다
  if (collapsed) {
    const on = (path: string) => location.pathname.startsWith(path)
    const divider = <div role="separator" className="w-6 my-1 border-t border-border" />
    return (
      <aside aria-label="사이드바(접힘)" className="w-[var(--icon-bar-width)] bg-surface-secondary border-r border-border flex flex-col items-center py-3 gap-1 flex-shrink-0">
        <IconButton icon={<PanelLeftOpen size={20} />} title="사이드바 펼치기" description="대화 목록과 메뉴를 펼칩니다" onClick={toggleSidebar} />
        {divider}
        <IconButton icon={<Search size={20} />} title="대화 검색" description="제목과 내용으로 이전 대화를 찾습니다 (Ctrl/⌘+K)" onClick={() => setSearchOpen(true)} />
        <IconButton icon={<PenSquare size={20} />} title="New Chat" description="새 대화를 시작합니다" onClick={handleNewChat} />
        <IconButton
          icon={<Bot size={20} />}
          title="My Agent"
          description={`내가 만든 에이전트를 관리하고 새 대화를 시작합니다 (발행 ${published.length}개)`}
          active={on('/agents')}
          badge={published.length > 0}
          onClick={() => navigate('/agents')}
        />
        <IconButton
          icon={<Rocket size={20} />}
          title="My Apps"
          description={`내가 배포한 웹앱을 실행하고 관리합니다 (${myApps.length}개)`}
          active={on('/apps')}
          badge={myApps.some((a) => a.status === 'running')}
          onClick={() => navigate('/apps')}
        />
        <IconButton icon={<Store size={20} />} title="App Store" description="공개된 앱을 둘러보고 실행합니다" active={on('/store')} onClick={() => navigate('/store')} />
        <div className="flex-1" />
        {divider}
        <IconButton icon={<Wrench size={20} />} title="Tools" description="에이전트가 쓰는 도구를 켜고 끕니다" active={on('/tools')} onClick={() => navigate('/tools')} />
        <IconButton icon={<Settings size={20} />} title="MCP Settings" description="외부 MCP 서버를 등록하고 관리합니다" active={on('/mcp')} onClick={() => navigate('/mcp')} />
        <IconButton icon={<Sparkles size={20} />} title="Skills" description="스킬을 설치하고 관리해 에이전트의 능력을 확장합니다" active={on('/skills')} onClick={() => navigate('/skills')} />
        <IconButton icon={<Brain size={20} />} title="Memory" description="에이전트가 기억하는 내용을 확인하고 정리합니다" active={on('/memory')} onClick={() => navigate('/memory')} />
        <IconButton icon={<Box size={20} />} title="Sandbox" description="작업공간(sandbox)의 상태와 파일을 관리합니다" active={on('/sandbox')} onClick={() => navigate('/sandbox')} />
        <IconButton icon={<BarChart3 size={20} />} title="Token Usage" description="토큰 사용량과 비용을 확인합니다" active={on('/admin/usage')} onClick={() => navigate('/admin/usage')} />
        {divider}
        <IconButton
          icon={<LogOut size={20} />}
          title="Logout"
          description={user?.display_name ? `${user.display_name} 계정에서 로그아웃합니다` : '로그아웃합니다'}
          onClick={() => { logout(); navigate('/auth') }}
        />
        {searchOpen && (
          <SearchDialog
            onClose={() => setSearchOpen(false)}
            onSelect={(id) => {
              setSearchOpen(false)
              setCurrentConversation(id)
              navigate(`/chat/${id}`)
            }}
          />
        )}
      </aside>
    )
  }

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
            title="대화 검색 (Ctrl/⌘+K)"
            aria-label="대화 검색"
            onClick={() => setSearchOpen(true)}
            className="w-7 h-7 rounded-[var(--radius-sm)] flex items-center justify-center
              text-content-secondary hover:text-content-primary hover:bg-surface-hover transition-colors"
          >
            <Search size={16} />
          </button>
          <button
            onClick={toggleSidebar}
            title="사이드바 접기"
            aria-label="사이드바 접기"
            aria-expanded={true}
            className="w-7 h-7 rounded-[var(--radius-sm)] flex items-center justify-center border-none bg-transparent cursor-pointer
              text-content-secondary hover:text-content-primary hover:bg-surface-hover transition-colors"
          >
            <PanelLeftClose size={16} />
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

        {/* My Apps: 배포한 웹앱 */}
        <div>
          <button
            onClick={() => setAppsOpen((o) => !o)}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-[var(--radius-md)]
              text-content-primary hover:bg-surface-hover transition-colors text-left"
            aria-expanded={appsOpen}
          >
            <span className="text-base">🚀</span>
            <span className="text-sm flex-1">My Apps</span>
            <span className="bg-accent-primary text-white text-[11px] font-semibold px-1.5 py-0.5 rounded-full min-w-[20px] text-center">
              {myApps.length}
            </span>
            <ChevronDown size={14} className={`text-content-muted transition-transform ${appsOpen ? 'rotate-180' : ''}`} />
          </button>
          {appsOpen && (
            <div className="mt-0.5 mb-1 space-y-0.5">
              {myApps.map((a) => (
                <button
                  key={a.id}
                  onClick={() => navigate(`/apps?open=${a.id}`)}
                  title={`${a.name} 실행`}
                  className="w-full flex items-center gap-2 pl-8 pr-3 py-1.5 rounded-[var(--radius-md)] text-left text-sm
                    text-content-secondary hover:bg-surface-hover hover:text-content-primary transition-colors"
                >
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${APP_DOT[a.status]}`} />
                  <span className="truncate flex-1">{a.name}</span>
                  <span className="text-[10px] text-content-tertiary flex-shrink-0">v{a.version}</span>
                </button>
              ))}
              {myApps.length === 0 && <p className="pl-8 pr-3 py-1 text-xs text-content-muted">배포한 앱이 없습니다</p>}
              <button
                onClick={() => navigate('/apps')}
                className="w-full pl-8 pr-3 py-1.5 rounded-[var(--radius-md)] text-left text-xs text-accent-primary hover:bg-surface-hover transition-colors"
              >
                앱 목록 보기
              </button>
            </div>
          )}
        </div>

        {/* App Store: 공개된 앱 둘러보기 */}
        <button
          onClick={() => navigate('/store')}
          className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-[var(--radius-md)]
            text-content-primary hover:bg-surface-hover transition-colors text-left"
        >
          <span className="text-base">🛍️</span>
          <span className="text-sm flex-1">App Store</span>
        </button>

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
      {searchOpen && (
        <SearchDialog
          onClose={() => setSearchOpen(false)}
          onSelect={(id) => {
            setSearchOpen(false)
            setCurrentConversation(id)
            navigate(`/chat/${id}`)
          }}
        />
      )}
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
      ) : conversation.space_id ? (
        <Layers size={14} className="flex-shrink-0 text-accent-primary" aria-label="스페이스 대화 (공용 sandbox)" />
      ) : (
        <MessageSquare size={14} className="flex-shrink-0" />
      )}
      <span className="text-sm truncate flex-1">{conversation.title}</span>
      <button
        onClick={onDelete}
        title="대화 삭제"
        aria-label="대화 삭제"
        className="opacity-0 group-hover:opacity-100 text-content-muted hover:text-accent-red transition-all flex-shrink-0"
      >
        <Trash2 size={12} />
      </button>
    </div>
  )
}

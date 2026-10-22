import { useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Home,
  MessageSquare,
  Clock,
  Globe,
  MoreVertical,
  Sun,
  Moon,
  Sliders,
  LayoutGrid,
  LogOut,
  BookOpen,
  Brain,
  Package,
} from 'lucide-react'
import { useThemeStore } from '../../store/themeStore'
import { useAuthStore } from '../../store/authStore'
import { schedulesApi } from '../../api/schedules'

interface IconButtonProps {
  icon: React.ReactNode
  title: string
  /** 툴팁에 제목 아래로 표시되는 설명 */
  description?: string
  active?: boolean
  onClick?: () => void
  /** 우상단 파란 점 (읽지 않은 알림) */
  badge?: boolean
}

/** 아이콘 오른쪽에 뜨는 툴팁 (hover / 키보드 포커스) */
function Tooltip({ title, description }: { title: string; description?: string }) {
  return (
    <span
      role="tooltip"
      className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-2 z-50
        w-max max-w-[220px] px-3 py-2 rounded-[var(--radius-md)] text-left
        bg-surface-tertiary text-content-primary border border-border shadow-lg
        opacity-0 translate-x-[-4px] transition-all duration-150 delay-300
        group-hover:opacity-100 group-hover:translate-x-0
        group-focus-visible:opacity-100 group-focus-visible:translate-x-0"
    >
      <span className="block text-xs font-semibold">{title}</span>
      {description && (
        <span className="block mt-0.5 text-[11px] leading-snug text-content-secondary whitespace-normal">
          {description}
        </span>
      )}
    </span>
  )
}

function IconButton({ icon, title, description, active, onClick, badge }: IconButtonProps) {
  return (
    <button
      onClick={onClick}
      aria-label={title}
      className={`group w-10 h-10 rounded-[var(--radius-md)] flex items-center justify-center
        text-content-secondary cursor-pointer transition-all duration-150
        border-none bg-transparent hover:bg-surface-hover hover:text-content-primary relative
        ${active ? 'bg-surface-active text-content-primary' : ''}`}
    >
      {icon}
      <Tooltip title={title} description={description} />
      {badge && <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-accent-primary ring-2 ring-surface-secondary" />}
    </button>
  )
}

export default function IconBar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { theme, toggleTheme } = useThemeStore()
  const { user, logout } = useAuthStore()
  // 예약 작업의 읽지 않은 결과가 있으면 시계 아이콘에 점을 표시한다
  const { data: unread } = useQuery({
    queryKey: ['schedules-unread'],
    queryFn: async () => (await schedulesApi.unreadCount()).data.count,
    refetchInterval: 30000,
    retry: false,
  })

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/' || location.pathname.startsWith('/chat')
    return location.pathname.startsWith(path)
  }

  const handleLogout = () => {
    logout()
    navigate('/auth')
  }

  return (
    <nav className="w-[var(--icon-bar-width)] bg-surface-secondary border-r border-border flex flex-col items-center py-3 gap-1 flex-shrink-0">
      {/* Main Navigation */}
      <IconButton
        icon={<Home size={20} />}
        title="Home"
        description="새 대화를 시작하고 채팅 화면으로 이동합니다"
        active={isActive('/')}
        onClick={() => navigate('/')}
      />
      <IconButton
        icon={<MessageSquare size={20} />}
        title="Tasks"
        description="작업 목록 (준비 중)"
        active={false}
      />
      <IconButton
        icon={<Clock size={20} />}
        title="예약"
        description="정해진 시간에 에이전트 작업을 자동 실행하도록 예약합니다"
        active={isActive('/schedules')}
        badge={(unread ?? 0) > 0}
        onClick={() => navigate('/schedules')}
      />
      <IconButton
        icon={<Package size={20} />}
        title="스킬"
        description="스킬과 플러그인을 설치하고 관리해 에이전트의 능력을 확장합니다"
        active={isActive('/skills') || isActive('/plugins')}
        onClick={() => navigate('/skills')}
      />
      <IconButton
        icon={<Globe size={20} />}
        title="Explore"
        description="탐색 (준비 중)"
        active={false}
      />
      <IconButton
        icon={<MoreVertical size={20} />}
        title="More"
        description="더보기 (준비 중)"
        active={false}
      />

      {/* Spacer */}
      <div className="flex-1" />

      {/* Theme Toggle */}
      <button
        onClick={toggleTheme}
        aria-label="테마 전환"
        className="group w-10 h-10 rounded-[var(--radius-md)] flex items-center justify-center
          text-content-secondary cursor-pointer transition-all duration-200
          border-none bg-transparent hover:bg-surface-hover hover:text-content-primary relative"
      >
        <Sun
          size={20}
          className={`absolute transition-all duration-300 ${
            theme === 'dark' ? 'opacity-100 rotate-0' : 'opacity-0 rotate-90'
          }`}
        />
        <Moon
          size={20}
          className={`absolute transition-all duration-300 ${
            theme === 'light' ? 'opacity-100 rotate-0' : 'opacity-0 -rotate-90'
          }`}
        />
        <Tooltip
          title={theme === 'dark' ? '라이트 모드로 전환' : '다크 모드로 전환'}
          description="단축키 Ctrl+Shift+L"
        />
      </button>

      {/* Settings */}
      <IconButton
        icon={<Brain size={20} />}
        title="Memory"
        description="에이전트가 기억하는 사용자 정보를 확인하고 관리합니다"
        active={isActive('/memory')}
        onClick={() => navigate('/memory')}
      />
      <IconButton
        icon={<BookOpen size={20} />}
        title="Wiki"
        description="대화에서 쌓은 지식을 정리한 개인 LLM 위키"
        active={isActive('/wiki')}
        onClick={() => navigate('/wiki')}
      />
      <IconButton
        icon={<Sliders size={20} />}
        title="MCP Settings"
        description="외부 도구를 연결하는 MCP 서버를 등록하고 관리합니다"
        active={isActive('/mcp')}
        onClick={() => navigate('/mcp')}
      />
      <IconButton
        icon={<LayoutGrid size={20} />}
        title="Sandbox"
        description="에이전트가 코드를 실행하는 격리 환경과 파일을 확인합니다"
        active={isActive('/sandbox')}
        onClick={() => navigate('/sandbox')}
      />

      {/* Divider */}
      <div className="h-2" />

      {/* User Avatar */}
      <button
        onClick={handleLogout}
        aria-label="로그아웃"
        className="group relative w-8 h-8 rounded-full bg-gradient-to-br from-accent-primary to-purple-500
          flex items-center justify-center text-xs font-semibold text-white cursor-pointer
          hover:opacity-90 transition-opacity"
      >
        {user?.display_name?.slice(0, 2).toUpperCase() || 'U'}
        <Tooltip title={user?.display_name || 'User'} description="클릭하면 로그아웃합니다" />
      </button>
    </nav>
  )
}
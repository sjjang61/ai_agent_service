import { useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Home,
  Layers,
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
  HardDrive,
} from 'lucide-react'
import { useThemeStore } from '../../store/themeStore'
import { useAuthStore } from '../../store/authStore'
import { schedulesApi } from '../../api/schedules'
import { IconButton, Tooltip } from './IconButton'

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
        icon={<Layers size={20} />}
        title="스페이스"
        description="프로젝트별 공간에서 문서 페이지를 작성하고 정리합니다"
        active={isActive('/spaces')}
        onClick={() => navigate('/spaces')}
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
        icon={<HardDrive size={20} />}
        title="Drive"
        description="내 파일 공간: 에이전트가 만든 산출물과 업로드한 파일을 폴더로 보관합니다"
        active={isActive('/drive')}
        onClick={() => navigate('/drive')}
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

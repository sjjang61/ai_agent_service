import { useNavigate, useLocation } from 'react-router-dom'
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
} from 'lucide-react'
import { useThemeStore } from '../../store/themeStore'
import { useAuthStore } from '../../store/authStore'

interface IconButtonProps {
  icon: React.ReactNode
  title: string
  active?: boolean
  onClick?: () => void
}

function IconButton({ icon, title, active, onClick }: IconButtonProps) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={`w-10 h-10 rounded-[var(--radius-md)] flex items-center justify-center
        text-content-secondary cursor-pointer transition-all duration-150
        border-none bg-transparent hover:bg-surface-hover hover:text-content-primary
        ${active ? 'bg-surface-active text-content-primary' : ''}`}
    >
      {icon}
    </button>
  )
}

export default function IconBar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { theme, toggleTheme } = useThemeStore()
  const { user, logout } = useAuthStore()

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
        active={isActive('/')}
        onClick={() => navigate('/')}
      />
      <IconButton
        icon={<MessageSquare size={20} />}
        title="Tasks"
        active={false}
      />
      <IconButton
        icon={<Clock size={20} />}
        title="History"
        active={false}
      />
      <IconButton
        icon={<Globe size={20} />}
        title="Explore"
        active={false}
      />
      <IconButton
        icon={<MoreVertical size={20} />}
        title="More"
        active={false}
      />

      {/* Spacer */}
      <div className="flex-1" />

      {/* Theme Toggle */}
      <button
        onClick={toggleTheme}
        title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode (Ctrl+Shift+L)`}
        className="w-10 h-10 rounded-[var(--radius-md)] flex items-center justify-center
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
      </button>

      {/* Settings */}
      <IconButton
        icon={<Brain size={20} />}
        title="Memory"
        active={isActive('/memory')}
        onClick={() => navigate('/memory')}
      />
      <IconButton
        icon={<BookOpen size={20} />}
        title="Wiki"
        active={isActive('/wiki')}
        onClick={() => navigate('/wiki')}
      />
      <IconButton
        icon={<Sliders size={20} />}
        title="MCP Settings"
        active={isActive('/mcp')}
        onClick={() => navigate('/mcp')}
      />
      <IconButton
        icon={<LayoutGrid size={20} />}
        title="Sandbox"
        active={isActive('/sandbox')}
        onClick={() => navigate('/sandbox')}
      />

      {/* Divider */}
      <div className="h-2" />

      {/* User Avatar */}
      <button
        onClick={handleLogout}
        title={`${user?.display_name || 'User'} - Click to logout`}
        className="w-8 h-8 rounded-full bg-gradient-to-br from-accent-primary to-purple-500
          flex items-center justify-center text-xs font-semibold text-white cursor-pointer
          hover:opacity-90 transition-opacity"
      >
        {user?.display_name?.slice(0, 2).toUpperCase() || 'U'}
      </button>
    </nav>
  )
}

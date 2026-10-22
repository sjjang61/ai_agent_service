import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Blocks, Box, Brain, Package, Search, Server, Wrench } from 'lucide-react'
import IconBar from '../layout/IconBar'
import { Tile } from './common'

export type CustomizeSection = 'tools' | 'mcp' | 'skills' | 'plugins' | 'memory' | 'sandbox'

interface Props {
  active: CustomizeSection
  /** 사이드바 '설치됨' 목록 (스킬·플러그인 화면에서만 넘긴다) */
  installed?: { id: string; name: string }[]
  onPickInstalled?: (name: string) => void
  children: React.ReactNode
}

const NAV: { key: CustomizeSection; label: string; icon: React.ReactNode; path: string }[] = [
  { key: 'tools', label: '도구', icon: <Wrench size={17} />, path: '/tools' },
  { key: 'mcp', label: 'MCP 설정', icon: <Server size={17} />, path: '/mcp' },
  { key: 'skills', label: '스킬', icon: <Package size={17} />, path: '/skills' },
  { key: 'plugins', label: '플러그인', icon: <Blocks size={17} />, path: '/plugins' },
  { key: 'memory', label: '메모리', icon: <Brain size={17} />, path: '/memory' },
  { key: 'sandbox', label: '샌드박스', icon: <Box size={17} />, path: '/sandbox' },
]

/** 맞춤 설정(플러그인/스킬) 공통 레이아웃: 아이콘 바 + 보조 사이드바 + 본문 */
export default function CustomizeLayout({ active, installed, onPickInstalled, children }: Props) {
  const hasInstalled = installed !== undefined
  const navigate = useNavigate()
  const [filter, setFilter] = useState('')
  const [searching, setSearching] = useState(false)
  const shown = (installed ?? []).filter((i) => i.name.toLowerCase().includes(filter.toLowerCase()))

  return (
    <div className="flex h-screen bg-surface-primary overflow-hidden">
      <IconBar />
      <aside className="w-[260px] flex-shrink-0 border-r border-border bg-surface-secondary flex flex-col overflow-hidden">
        <div className="h-[52px] flex items-center justify-between px-4 flex-shrink-0">
          <h2 className="text-[16px] font-semibold text-content-primary">맞춤 설정</h2>
          {hasInstalled && <button
            onClick={() => { setSearching((s) => !s); setFilter('') }}
            title="설치됨 목록 검색"
            aria-label="설치됨 목록 검색"
            className="text-content-tertiary hover:text-content-primary border-none bg-transparent cursor-pointer"
          >
            <Search size={16} />
          </button>}
        </div>
        {hasInstalled && searching && (
          <div className="px-3 pb-2">
            <input
              autoFocus
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="검색"
              className="w-full px-3 py-1.5 bg-surface-primary border border-border rounded-[var(--radius-md)] text-[13px] text-content-primary focus:outline-none focus:border-accent-primary"
            />
          </div>
        )}
        <nav className="px-2 space-y-0.5">
          {NAV.map((n) => (
            <button
              key={n.key}
              onClick={() => navigate(n.path)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-[var(--radius-md)] text-[14px] border-none cursor-pointer transition-colors
                ${active === n.key ? 'bg-surface-active text-content-primary' : 'bg-transparent text-content-secondary hover:bg-surface-hover'}`}
            >
              {n.icon}
              {n.label}
            </button>
          ))}
        </nav>
        {hasInstalled ? (
          <>
        <div className="px-5 pt-5 pb-1.5 text-xs text-content-tertiary">설치됨</div>
        <div className="flex-1 overflow-y-auto px-2 pb-3">
          {shown.length === 0 ? (
            <div className="px-3 py-2 text-[13px] text-content-muted">{installed.length ? '결과 없음' : '설치된 항목이 없습니다'}</div>
          ) : (
            shown.map((i) => (
              <button
                key={i.id}
                onClick={() => onPickInstalled?.(i.name)}
                className="w-full flex items-center gap-2.5 px-3 py-1.5 rounded-[var(--radius-md)] text-[13px] text-content-primary
                  bg-transparent border-none cursor-pointer hover:bg-surface-hover text-left"
              >
                <Tile name={i.name} size={22} />
                <span className="truncate">{i.name}</span>
              </button>
            ))
          )}
        </div>
          </>
        ) : (
          <div className="flex-1" />
        )}
      </aside>
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">{children}</main>
    </div>
  )
}

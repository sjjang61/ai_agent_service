import { useEffect } from 'react'
import { X } from 'lucide-react'

interface Props {
  title: string
  subtitle?: string
  icon?: React.ReactNode
  onClose: () => void
  children: React.ReactNode
}

/** 채팅 우측 패널 공통 틀 (Artifacts, 문서 등): 머리글 + 스크롤 본문. Esc 로 닫는다. */
export default function RightPanel({ title, subtitle, icon, onClose, children }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null
      const typing = el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)
      if (e.key === 'Escape' && !typing) onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <aside aria-label={title} className="w-[420px] flex-shrink-0 border-l border-border flex flex-col h-screen overflow-hidden bg-surface-primary">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-surface-secondary">
        {icon && <span className="text-content-secondary flex-shrink-0">{icon}</span>}
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-content-primary truncate">{title}</div>
          {subtitle && <div className="text-[11px] text-content-tertiary truncate">{subtitle}</div>}
        </div>
        <button onClick={onClose} aria-label="패널 닫기" title="닫기 (Esc)" className="text-content-muted hover:text-content-primary transition-colors border-none bg-transparent cursor-pointer">
          <X size={16} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">{children}</div>
    </aside>
  )
}

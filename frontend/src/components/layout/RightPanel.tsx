import { useEffect } from 'react'
import { X } from 'lucide-react'

interface Props {
  title: string
  subtitle?: string
  icon?: React.ReactNode
  onClose: () => void
  /** 앱 미리보기처럼 넓은 화면이 필요한 패널 */
  wide?: boolean
  /** true 면 화면이 좁아도 오른쪽에 겹쳐 띄우지 않고 흐름 안에 둔다 (데스크톱에서 브라우저 오른쪽에 배치할 때) */
  inline?: boolean
  /** 닫기 버튼 앞에 놓을 추가 버튼 */
  headerExtra?: React.ReactNode
  children: React.ReactNode
}

/** 채팅 우측 패널 공통 틀 (Artifacts, 문서 등): 머리글 + 스크롤 본문. Esc 로 닫는다. */
export default function RightPanel({ title, subtitle, icon, onClose, wide, inline, headerExtra, children }: Props) {
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
    // 화면이 좁으면(데스크톱 앱의 분할 창 등) 채팅을 찌그러뜨리지 않도록 오른쪽에 겹쳐서 띄운다
    <aside aria-label={title} className={`${wide ? 'w-[46vw] min-w-[420px] max-w-[900px]' : 'w-[420px]'} flex-shrink-0 border-l border-border flex flex-col h-screen overflow-hidden bg-surface-primary ${inline ? '' : 'max-[1279px]:fixed max-[1279px]:right-0 max-[1279px]:top-0 max-[1279px]:z-30 max-[1279px]:max-w-[92vw] max-[1279px]:shadow-2xl'}`}>
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-surface-secondary">
        {icon && <span className="text-content-secondary flex-shrink-0">{icon}</span>}
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-content-primary truncate">{title}</div>
          {subtitle && <div className="text-[11px] text-content-tertiary truncate">{subtitle}</div>}
        </div>
        {headerExtra}
        <button onClick={onClose} aria-label="패널 닫기" title="닫기 (Esc)" className="text-content-muted hover:text-content-primary transition-colors border-none bg-transparent cursor-pointer">
          <X size={16} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">{children}</div>
    </aside>
  )
}

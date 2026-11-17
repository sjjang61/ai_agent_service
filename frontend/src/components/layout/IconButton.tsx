/** 좌측 아이콘 막대와 접힌 사이드바가 함께 쓰는 아이콘 버튼 + 툴팁 */

export interface IconButtonProps {
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
export function Tooltip({ title, description }: { title: string; description?: string }) {
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
        <span className="block mt-0.5 text-[11px] leading-snug text-content-secondary whitespace-normal break-keep">
          {description}
        </span>
      )}
    </span>
  )
}

export function IconButton({ icon, title, description, active, onClick, badge }: IconButtonProps) {
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

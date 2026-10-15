import { createPortal } from 'react-dom'
import { BookmarkPlus } from 'lucide-react'

interface SelectionPosition {
  top: number
  left: number
  width: number
}

interface SelectionTooltipProps {
  selectedText: string
  position: SelectionPosition
  onSaveToWiki: () => void
  onClose: () => void
}

export default function SelectionTooltip({
  selectedText,
  position,
  onSaveToWiki,
  onClose,
}: SelectionTooltipProps) {
  if (!selectedText || !position) return null

  const content = (
    <div
      className="fixed z-50 animate-in fade-in slide-in-from-bottom-2 duration-200"
      style={{
        top: `${position.top}px`,
        left: `${position.left}px`,
        transform: 'translateX(-50%)',
      }}
    >
      <button
        onClick={(e) => {
          e.stopPropagation()
          onSaveToWiki()
        }}
        className="flex items-center gap-2 px-3 py-2 rounded-[var(--radius-md)] bg-surface-primary border border-border shadow-lg hover:bg-surface-secondary transition-colors"
      >
        <BookmarkPlus size={16} className="text-accent-primary" />
        <span className="text-sm font-medium text-content-primary">
          Wiki에 저장
        </span>
      </button>
    </div>
  )

  return createPortal(content, document.body)
}

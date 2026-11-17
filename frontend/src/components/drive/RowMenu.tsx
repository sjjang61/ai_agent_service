import { useEffect, useRef, useState } from 'react'
import { MoreHorizontal } from 'lucide-react'

export interface MenuItem {
  label: string
  onClick: () => void
  danger?: boolean
  disabled?: boolean
  title?: string
}

/** 행 오른쪽 ⋯ 메뉴. 바깥 클릭·Esc 로 닫히고, 열린 동안 ↑↓ 로 항목을 고른다. */
export default function RowMenu({ items, label }: { items: MenuItem[]; label: string }) {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const btn = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { setOpen(false); btn.current?.focus() }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault()
        const els = Array.from(box.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not(:disabled)') ?? [])
        const i = els.indexOf(document.activeElement as HTMLButtonElement)
        els[(i + (e.key === 'ArrowDown' ? 1 : -1) + els.length) % els.length]?.focus()
      }
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    box.current?.querySelector<HTMLButtonElement>('[role="menuitem"]:not(:disabled)')?.focus()
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey) }
  }, [open])

  return (
    <div ref={box} className="relative">
      <button ref={btn} onClick={(e) => { e.stopPropagation(); setOpen((v) => !v) }} aria-haspopup="menu" aria-expanded={open} aria-label={`${label} 메뉴`}
        className="p-1.5 rounded-md border-none bg-transparent text-content-tertiary hover:text-content-primary hover:bg-surface-hover cursor-pointer">
        <MoreHorizontal size={16} />
      </button>
      {open && (
        <div role="menu" aria-label={`${label} 메뉴`} className="absolute right-0 top-full mt-1 z-30 w-40 py-1.5 rounded-xl border border-border bg-surface-primary shadow-xl">
          {items.map((it) => (
            <button key={it.label} role="menuitem" disabled={it.disabled} title={it.title}
              onClick={(e) => { e.stopPropagation(); setOpen(false); it.onClick() }}
              className={`w-full text-left px-4 py-2 text-sm border-none bg-transparent cursor-pointer hover:bg-surface-hover focus:bg-surface-hover focus:outline-none disabled:opacity-40 disabled:cursor-not-allowed ${it.danger ? 'text-accent-red' : 'text-content-primary'}`}>
              {it.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

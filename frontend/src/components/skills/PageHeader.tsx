import { useEffect, useRef, useState } from 'react'
import { ChevronDown, RefreshCw, Search, Settings } from 'lucide-react'

interface MenuItem { label: string; hint?: string; onClick: () => void }

interface Props {
  title: string
  subtitle: string
  query: string
  onQuery: (q: string) => void
  placeholder: string
  onRefresh: () => void
  refreshing?: boolean
  onSettings?: { title: string; run: () => void }
  addItems: MenuItem[]
}

/** 제목 + 검색 + 새로고침 + (설정) + 추가 드롭다운 */
export default function PageHeader({ title, subtitle, query, onQuery, placeholder, onRefresh, refreshing, onSettings, addItems }: Props) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const iconBtn = 'w-9 h-9 flex items-center justify-center rounded-full text-content-secondary hover:bg-surface-hover hover:text-content-primary border-none bg-transparent cursor-pointer'
  return (
    <div className="px-8 pt-8 pb-4 flex-shrink-0">
      <div className="flex items-center gap-3">
        <h1 className="text-[28px] font-semibold text-content-primary flex-1">{title}</h1>
        <div className="flex items-center gap-2 w-[300px] px-3.5 py-2 border border-border rounded-full bg-surface-primary focus-within:border-accent-primary">
          <Search size={15} className="text-content-tertiary" />
          <input
            value={query}
            onChange={(e) => onQuery(e.target.value)}
            placeholder={placeholder}
            className="flex-1 bg-transparent border-none outline-none text-[13px] text-content-primary placeholder:text-content-muted"
          />
        </div>
        <button onClick={onRefresh} title="새로고침" aria-label="새로고침" className={iconBtn}>
          <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
        </button>
        {onSettings && (
          <button onClick={onSettings.run} title={onSettings.title} aria-label={onSettings.title} className={iconBtn}>
            <Settings size={16} />
          </button>
        )}
        <div className="relative" ref={ref}>
          <button
            onClick={() => setOpen((o) => !o)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-content-primary text-surface-primary text-[14px] font-medium border-none cursor-pointer hover:opacity-90"
          >
            추가 <ChevronDown size={15} />
          </button>
          {open && (
            <div className="absolute right-0 mt-2 w-[240px] z-40 bg-surface-primary border border-border rounded-[var(--radius-lg)] shadow-xl p-1.5">
              {addItems.map((it) => (
                <button
                  key={it.label}
                  onClick={() => { setOpen(false); it.onClick() }}
                  className="w-full text-left px-3 py-2 rounded-[var(--radius-md)] hover:bg-surface-hover border-none bg-transparent cursor-pointer"
                >
                  <div className="text-[13px] text-content-primary">{it.label}</div>
                  {it.hint && <div className="text-xs text-content-tertiary">{it.hint}</div>}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      <p className="mt-1 text-[14px] text-content-secondary">{subtitle}</p>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronRight, Loader2, X } from 'lucide-react'
import { driveApi, type DriveNode } from '../../api/drive'
import { NodeIcon, formatBytes } from './driveUtils'

/** Drive 에서 파일을 골라 채팅에 첨부한다. 폴더를 눌러 들어가고, 파일은 체크해서 여러 개 고를 수 있다. */
export default function DriveFilePickerDialog({ maxSelect, onPick, onClose, title = 'Drive 에서 첨부', confirmLabel = '첨부', extensions }: {
  maxSelect: number
  onPick: (files: DriveNode[]) => void
  onClose: () => void
  title?: string
  confirmLabel?: string
  /** 있으면 이 확장자의 파일만 고를 수 있다 (소문자, 점 없이). 예: ['zip'] */
  extensions?: string[]
}) {
  const [current, setCurrent] = useState('root')
  const [picked, setPicked] = useState<Map<string, DriveNode>>(new Map())
  const { data, isLoading, isError } = useQuery({ queryKey: ['drive', 'file-picker', current], queryFn: () => driveApi.list(current), retry: false })
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const selectable = (n: DriveNode) => !extensions || extensions.includes(n.name.split('.').pop()?.toLowerCase() ?? '')
  const toggle = (n: DriveNode) => setPicked((m) => {
    const next = new Map(m)
    if (next.has(n.id)) next.delete(n.id)
    else if (next.size < maxSelect) next.set(n.id, n)
    return next
  })

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-[12vh] px-4" onMouseDown={onClose}>
      <div role="dialog" aria-label={title} onMouseDown={(e) => e.stopPropagation()} className="w-full max-w-md rounded-xl border border-border bg-surface-primary shadow-xl">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
          <h2 className="flex-1 m-0 text-sm font-semibold text-content-primary">{title}</h2>
          <button onClick={onClose} aria-label="닫기" className="p-1 border-none bg-transparent text-content-muted hover:text-content-primary cursor-pointer"><X size={15} /></button>
        </div>
        <nav aria-label="현재 위치" className="flex flex-wrap items-center gap-0.5 px-4 py-2 text-xs text-content-secondary border-b border-border">
          {(data?.breadcrumb ?? []).map((c, i, arr) => (
            <span key={c.id} className="flex items-center gap-0.5">
              {i > 0 && <ChevronRight size={12} className="text-content-tertiary" />}
              {i === arr.length - 1 ? <span className="text-content-primary font-medium">{c.name}</span>
                : <button onClick={() => setCurrent(c.id)} className="border-none bg-transparent p-0 text-content-secondary hover:text-content-primary cursor-pointer">{c.name}</button>}
            </span>
          ))}
        </nav>
        <ul className="m-0 p-1 list-none h-72 overflow-auto">
          {isLoading && <li className="flex items-center gap-2 p-3 text-sm text-content-muted"><Loader2 size={14} className="animate-spin" /> 불러오는 중...</li>}
          {isError && <li className="p-3 text-sm text-accent-red">Drive 를 불러오지 못했습니다</li>}
          {!isLoading && !isError && (data?.nodes.length ?? 0) === 0 && <li className="p-3 text-sm text-content-muted">비어 있습니다</li>}
          {(data?.nodes ?? []).map((n) => (
            <li key={n.id}>
              {n.type === 'folder' ? (
                <button onClick={() => setCurrent(n.id)} className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-left text-content-primary border-none bg-transparent hover:bg-surface-hover cursor-pointer">
                  <NodeIcon node={n} /> <span className="truncate flex-1">{n.name}</span> <ChevronRight size={14} className="text-content-tertiary" />
                </button>
              ) : (
                <label className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm hover:bg-surface-hover ${selectable(n) ? 'text-content-primary cursor-pointer' : 'text-content-muted opacity-50 cursor-not-allowed'}`} title={selectable(n) ? undefined : `${(extensions ?? []).join(', ')} 파일만 선택할 수 있습니다`}>
                  <input type="checkbox" checked={picked.has(n.id)} onChange={() => toggle(n)} disabled={!selectable(n) || (!picked.has(n.id) && picked.size >= maxSelect)} className="w-4 h-4 accent-[var(--accent-primary)]" />
                  <NodeIcon node={n} /> <span className="truncate flex-1">{n.name}</span>
                  <span className="text-xs text-content-tertiary">{formatBytes(n.size_bytes ?? 0)}</span>
                </label>
              )}
            </li>
          ))}
        </ul>
        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-border">
          <span className="flex-1 text-xs text-content-tertiary">{picked.size > 0 ? `${picked.size}개 선택` : `최대 ${maxSelect}개`}</span>
          <button onClick={onClose} className="px-3 py-1.5 rounded-lg text-sm border border-border bg-transparent text-content-secondary hover:bg-surface-hover cursor-pointer">취소</button>
          <button onClick={() => onPick([...picked.values()])} disabled={picked.size === 0} className="px-3 py-1.5 rounded-lg text-sm border-none bg-accent-primary text-white cursor-pointer disabled:opacity-50">{confirmLabel}</button>
        </div>
      </div>
    </div>
  )
}

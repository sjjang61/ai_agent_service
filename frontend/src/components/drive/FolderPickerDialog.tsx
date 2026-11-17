import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronRight, Loader2, X } from 'lucide-react'
import { driveApi } from '../../api/drive'
import { NodeIcon } from './driveUtils'

/** 이동할 폴더를 고르는 대화상자. 폴더만 보여 주고, 옮기려는 폴더 자신(과 그 하위)은 숨긴다 (서버도 거부한다). */
export default function FolderPickerDialog({ title, exclude, startId, busy, error, confirmLabel = '여기로 이동', onPick, onClose }: {
  title: string
  confirmLabel?: string
  exclude: string[]
  startId: string
  busy: boolean
  error: string | null
  onPick: (folderId: string) => void
  onClose: () => void
}) {
  const [current, setCurrent] = useState(startId)
  const { data, isLoading, isError } = useQuery({
    queryKey: ['drive', 'picker', current],
    queryFn: () => driveApi.list(current, { foldersOnly: true }),
    retry: false,
  })
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const folders = (data?.nodes ?? []).filter((n) => !exclude.includes(n.id))
  const inExcluded = (data?.breadcrumb ?? []).some((c) => exclude.includes(c.id))

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
        <ul className="m-0 p-1 list-none h-64 overflow-auto">
          {isLoading && <li className="flex items-center gap-2 p-3 text-sm text-content-muted"><Loader2 size={14} className="animate-spin" /> 불러오는 중...</li>}
          {isError && <li className="p-3 text-sm text-accent-red">폴더를 불러오지 못했습니다</li>}
          {!isLoading && !isError && folders.length === 0 && <li className="p-3 text-sm text-content-muted">하위 폴더가 없습니다</li>}
          {folders.map((f) => (
            <li key={f.id}>
              <button onClick={() => setCurrent(f.id)} className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-left text-content-primary border-none bg-transparent hover:bg-surface-hover cursor-pointer">
                <NodeIcon node={f} /> <span className="truncate flex-1">{f.name}</span> <ChevronRight size={14} className="text-content-tertiary" />
              </button>
            </li>
          ))}
        </ul>
        {error && <p role="alert" className="m-0 px-4 pb-2 text-xs text-accent-red">{error}</p>}
        <div className="flex justify-end gap-2 px-4 py-3 border-t border-border">
          <button onClick={onClose} className="px-3 py-1.5 rounded-lg text-sm border border-border bg-transparent text-content-secondary hover:bg-surface-hover cursor-pointer">취소</button>
          <button onClick={() => onPick(current)} disabled={busy || inExcluded || !data}
            className="px-3 py-1.5 rounded-lg text-sm border-none bg-accent-primary text-white cursor-pointer disabled:opacity-50 flex items-center gap-1.5">
            {busy && <Loader2 size={13} className="animate-spin" />} {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

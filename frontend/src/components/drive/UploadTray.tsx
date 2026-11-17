import { AlertCircle, Check, Loader2, RotateCw, X } from 'lucide-react'

export interface UploadItem {
  id: string
  name: string
  progress: number
  status: 'queued' | 'uploading' | 'done' | 'error'
  error?: string
}

/** 우측 하단 업로드 진행 목록: 파일별 진행률, 취소(대기·진행 중), 재시도(실패), 닫기(완료·실패) */
export default function UploadTray({ items, onCancel, onRetry, onDismiss }: {
  items: UploadItem[]
  onCancel: (id: string) => void
  onRetry: (id: string) => void
  onDismiss: (id: string) => void
}) {
  if (items.length === 0) return null
  return (
    <div role="status" aria-live="polite" aria-label="업로드 진행" className="fixed right-4 bottom-4 z-40 w-80 max-h-72 overflow-auto rounded-xl border border-border bg-surface-primary shadow-xl p-2 space-y-1">
      {items.map((it) => (
        <div key={it.id} className="px-2 py-1.5 rounded-lg">
          <div className="flex items-center gap-2 text-xs">
            {it.status === 'done' ? <Check size={14} className="text-accent-green flex-shrink-0" />
              : it.status === 'error' ? <AlertCircle size={14} className="text-accent-red flex-shrink-0" />
              : <Loader2 size={14} className={`flex-shrink-0 text-content-tertiary ${it.status === 'uploading' ? 'animate-spin' : ''}`} />}
            <span className="flex-1 min-w-0 truncate text-content-primary" title={it.name}>{it.name}</span>
            {it.status === 'error' && <button onClick={() => onRetry(it.id)} aria-label={`${it.name} 다시 시도`} className="p-0.5 border-none bg-transparent text-content-secondary hover:text-content-primary cursor-pointer"><RotateCw size={13} /></button>}
            {(it.status === 'queued' || it.status === 'uploading') && <button onClick={() => onCancel(it.id)} aria-label={`${it.name} 취소`} className="p-0.5 border-none bg-transparent text-content-secondary hover:text-content-primary cursor-pointer"><X size={13} /></button>}
            {(it.status === 'done' || it.status === 'error') && <button onClick={() => onDismiss(it.id)} aria-label={`${it.name} 목록에서 지우기`} className="p-0.5 border-none bg-transparent text-content-tertiary hover:text-content-primary cursor-pointer"><X size={13} /></button>}
          </div>
          {it.status === 'uploading' && (
            <div className="mt-1 h-1 rounded bg-surface-tertiary overflow-hidden" role="progressbar" aria-valuenow={Math.round(it.progress * 100)} aria-valuemin={0} aria-valuemax={100}>
              <div className="h-full bg-accent-primary transition-[width]" style={{ width: `${Math.round(it.progress * 100)}%` }} />
            </div>
          )}
          {it.status === 'error' && <p className="m-0 mt-0.5 text-[11px] text-accent-red break-words">{it.error}</p>}
        </div>
      ))}
    </div>
  )
}

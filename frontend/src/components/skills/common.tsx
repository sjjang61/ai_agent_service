import { T } from './typography'
import { useEffect, useState } from 'react'
import { Check, Loader2, Trash2, X } from 'lucide-react'
import axios from 'axios'

export function errorText(err: unknown, fallback: string): string {
  const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null
  return typeof detail === 'string' ? detail : fallback
}

const TILE_COLORS = ['#3b82f6', '#a855f7', '#22c55e', '#f97316', '#ef4444', '#06b6d4', '#f59e0b', '#ec4899']

/** 이름 첫 글자로 만든 컬러 타일 (이름이 같으면 항상 같은 색) */
export function Tile({ name, size = 44 }: { name: string; size?: number }) {
  let h = 0
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0
  const color = TILE_COLORS[h % TILE_COLORS.length]
  return (
    <span
      className="flex items-center justify-center rounded-[var(--radius-md)] font-semibold text-white flex-shrink-0 select-none"
      style={{ width: size, height: size, background: color, fontSize: size * 0.42 }}
    >
      {name.charAt(0).toUpperCase()}
    </span>
  )
}

interface CardProps {
  name: string
  description?: string | null
  meta?: string
  active: boolean
  onToggle: () => void
  onDelete: () => void
}

/** 목록 카드: 타일 + 이름/설명 + 활성 체크 (마우스를 올리면 삭제 버튼) */
export function ItemCard({ name, description, meta, active, onToggle, onDelete }: CardProps) {
  return (
    <div
      className={`group flex items-center gap-3.5 p-3.5 rounded-[var(--radius-lg)] hover:bg-surface-hover transition-colors
        ${active ? '' : 'opacity-55'}`}
    >
      <Tile name={name} />
      <div className="min-w-0 flex-1">
        <div className={`${T.itemTitle} truncate`} title={name}>
          {name}
          {meta && <span className="ml-2 text-xs font-normal text-content-tertiary">{meta}</span>}
        </div>
        <div className={`${T.itemDesc} truncate`} title={description ?? ''}>
          {description || '설명 없음'}
        </div>
      </div>
      <button
        onClick={onDelete}
        title="삭제"
        aria-label={`${name} 삭제`}
        className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 text-content-muted hover:text-accent-red
          transition-all border-none bg-transparent cursor-pointer"
      >
        <Trash2 size={15} />
      </button>
      <button
        onClick={onToggle}
        title={active ? '사용 중 — 클릭하면 비활성화' : '비활성 — 클릭하면 사용'}
        aria-pressed={active}
        className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 cursor-pointer transition-colors border
          ${active ? 'bg-accent-primary border-accent-primary text-white' : 'bg-transparent border-border text-transparent hover:text-content-muted'}`}
      >
        <Check size={14} strokeWidth={3} />
      </button>
    </div>
  )
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onMouseDown={onClose}>
      <div
        className="w-full max-w-[560px] max-h-[90vh] overflow-y-auto bg-surface-primary border border-border rounded-[var(--radius-xl)] p-6 shadow-xl"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-[16px] font-semibold text-content-primary">{title}</h2>
          <button onClick={onClose} aria-label="닫기" className="text-content-tertiary hover:text-content-primary border-none bg-transparent cursor-pointer">
            <X size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

export const inputCls =
  'w-full px-3.5 py-2.5 bg-surface-secondary border border-border rounded-[var(--radius-md)] text-[13px] text-content-primary placeholder:text-content-muted focus:outline-none focus:border-accent-primary transition-colors'

export const primaryBtn =
  'flex items-center justify-center gap-2 px-4 py-2.5 bg-accent-primary hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-[var(--radius-md)] text-[13px] font-medium transition-colors border-none cursor-pointer'

/** GitHub URL 입력 → 설치 다이얼로그 (스킬/플러그인 공용) */
export function GithubDialog(props: {
  title: string
  hint: string
  placeholder: string
  onInstall: (url: string) => Promise<string>
  onClose: () => void
}) {
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return
    setBusy(true)
    setError(null)
    try {
      await props.onInstall(url.trim())
      props.onClose()
    } catch (err) {
      setError(errorText(err, '설치하지 못했습니다'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title={props.title} onClose={props.onClose}>
      <form onSubmit={submit} className="space-y-3">
        <p className="text-[13px] text-content-secondary">{props.hint}</p>
        <input autoFocus value={url} onChange={(e) => setUrl(e.target.value)} placeholder={props.placeholder} className={inputCls} />
        {error && <p className="text-[13px] text-accent-red">{error}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={props.onClose} className="px-4 py-2.5 text-[13px] text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer">
            취소
          </button>
          <button type="submit" disabled={busy || !url.trim()} className={primaryBtn}>
            {busy && <Loader2 size={14} className="animate-spin" />}
            설치
          </button>
        </div>
      </form>
    </Modal>
  )
}

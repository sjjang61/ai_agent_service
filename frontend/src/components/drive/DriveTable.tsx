import { useEffect, useRef, useState } from 'react'
import { ArrowDown, ArrowUp, Folder } from 'lucide-react'
import type { DriveNode, SortKey } from '../../api/drive'
import { formatDateTimeMinute } from '../../utils/time'
import RowMenu, { type MenuItem } from './RowMenu'
import { NodeIcon, formatBytes } from './driveUtils'

/** 이름을 행 안에서 편집한다. Enter 저장 · Esc 취소 · 포커스를 잃으면 저장. 파일은 확장자를 뺀 부분만 먼저 선택한다. */
function InlineName({ initial, isFile, error, onSubmit, onCancel }: {
  initial: string; isFile: boolean; error: string | null; onSubmit: (v: string) => void; onCancel: () => void
}) {
  const [value, setValue] = useState(initial)
  const ref = useRef<HTMLInputElement>(null)
  const done = useRef(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.focus()
    const dot = isFile ? initial.lastIndexOf('.') : -1
    el.setSelectionRange(0, dot > 0 ? dot : initial.length)
  }, [initial, isFile])
  const finish = (save: boolean) => {
    if (done.current) return
    done.current = true
    if (save && value.trim() && value !== initial) onSubmit(value)
    else onCancel()
  }
  return (
    <div className="flex-1 min-w-0">
      <input ref={ref} value={value} aria-label="이름" aria-invalid={!!error}
        onChange={(e) => { setValue(e.target.value); done.current = false }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.nativeEvent.isComposing) { e.preventDefault(); finish(true) }
          else if (e.key === 'Escape') { e.preventDefault(); finish(false) }
        }}
        onBlur={() => finish(true)}
        onClick={(e) => e.stopPropagation()}
        className="w-full px-2 py-1 rounded-md border border-accent-primary bg-surface-primary text-sm text-content-primary outline-none" />
      {error && <p role="alert" className="m-0 mt-0.5 text-[11px] text-accent-red">{error}</p>}
    </div>
  )
}

function SortHeader({ label, k, sort, onSort, className }: { label: string; k: SortKey; sort: { key: SortKey; desc: boolean }; onSort: (k: SortKey) => void; className?: string }) {
  const active = sort.key === k
  return (
    <button onClick={() => onSort(k)} aria-label={`${label} 정렬`} className={`inline-flex items-center gap-1 border-none bg-transparent p-0 text-xs font-medium cursor-pointer hover:text-content-primary ${active ? 'text-content-primary' : 'text-content-secondary'} ${className ?? ''}`}>
      {label}{active && (sort.desc ? <ArrowDown size={11} /> : <ArrowUp size={11} />)}
    </button>
  )
}

export default function DriveTable({ nodes, selected, onToggle, onToggleAll, sort, onSort, renamingId, renameError, onRenameSubmit, onRenameCancel,
  creating, createError, onCreateSubmit, onCreateCancel, onOpen, menuFor, emptyHint }: {
  nodes: DriveNode[]
  selected: Set<string>
  onToggle: (id: string) => void
  onToggleAll: () => void
  sort: { key: SortKey; desc: boolean }
  onSort: (k: SortKey) => void
  renamingId: string | null
  renameError: string | null
  onRenameSubmit: (id: string, name: string) => void
  onRenameCancel: () => void
  creating: boolean
  createError: string | null
  onCreateSubmit: (name: string) => void
  onCreateCancel: () => void
  onOpen: (n: DriveNode) => void
  menuFor: (n: DriveNode) => MenuItem[]
  emptyHint: string
}) {
  const all = nodes.length > 0 && nodes.every((n) => selected.has(n.id))
  const some = !all && nodes.some((n) => selected.has(n.id))
  const headCheck = useRef<HTMLInputElement>(null)
  useEffect(() => { if (headCheck.current) headCheck.current.indeterminate = some }, [some])

  const cell = 'py-3 text-sm'
  return (
    <div className="rounded-xl border border-border bg-surface-primary" role="table" aria-label="파일 목록">
      <div role="row" className="flex items-center gap-3 px-4 py-3 border-b border-border">
        <input ref={headCheck} type="checkbox" checked={all} onChange={onToggleAll} aria-label="전체 선택" className="w-4 h-4 cursor-pointer accent-[var(--accent-primary)]" />
        <div role="columnheader" className="flex-1 min-w-0"><SortHeader label="이름" k="name" sort={sort} onSort={onSort} /></div>
        <div role="columnheader" className="w-24 text-right"><SortHeader label="크기" k="size" sort={sort} onSort={onSort} /></div>
        <div role="columnheader" className="w-36 text-right"><SortHeader label="수정일시" k="updated" sort={sort} onSort={onSort} /></div>
        <div className="w-8" aria-hidden />
      </div>

      {creating && (
        <div role="row" className="flex items-center gap-3 px-4 py-2 border-b border-border bg-surface-secondary">
          <span className="w-4" />
          <div className="flex-1 min-w-0 flex items-center gap-2.5"><Folder size={16} className="text-accent-blue flex-shrink-0" aria-hidden />
            <InlineName initial="새 폴더" isFile={false} error={createError} onSubmit={onCreateSubmit} onCancel={onCreateCancel} /></div>
          <span className="w-24" /><span className="w-36" /><span className="w-8" />
        </div>
      )}

      {nodes.length === 0 && !creating && <div className="px-4 py-14 text-center text-sm text-content-muted">{emptyHint}</div>}

      {nodes.map((n) => {
        const sel = selected.has(n.id)
        return (
          <div key={n.id} role="row" aria-selected={sel} className={`group flex items-center gap-3 px-4 border-b last:border-b-0 border-border ${sel ? 'bg-accent-primary/10' : 'hover:bg-surface-hover'}`}>
            <input type="checkbox" checked={sel} onChange={() => onToggle(n.id)} aria-label={`${n.name} 선택`} className="w-4 h-4 cursor-pointer accent-[var(--accent-primary)]" />
            <div role="cell" className={`flex-1 min-w-0 flex items-center gap-2.5 ${cell}`}>
              <NodeIcon node={n} />
              {renamingId === n.id ? (
                <InlineName initial={n.name} isFile={n.type === 'file'} error={renameError} onSubmit={(v) => onRenameSubmit(n.id, v)} onCancel={onRenameCancel} />
              ) : (
                <button onClick={() => onOpen(n)} title={n.type === 'folder' ? '폴더 열기' : '다운로드'} className="min-w-0 truncate text-left border-none bg-transparent p-0 text-sm text-content-primary cursor-pointer hover:underline">{n.name}</button>
              )}
            </div>
            <div role="cell" className={`w-24 text-right text-xs text-content-tertiary ${cell}`}>{n.type === 'file' ? formatBytes(n.size_bytes ?? 0) : '—'}</div>
            <div role="cell" className={`w-36 text-right text-xs text-content-tertiary whitespace-nowrap ${cell}`}>{n.updated_at ? formatDateTimeMinute(n.updated_at) : ''}</div>
            <div role="cell" className="w-8 flex justify-end"><RowMenu label={n.name} items={menuFor(n)} /></div>
          </div>
        )
      })}
    </div>
  )
}

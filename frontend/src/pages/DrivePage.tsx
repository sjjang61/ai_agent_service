import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronRight, FolderPlus, HardDrive, Loader2, RefreshCw, Trash2, Upload } from 'lucide-react'
import IconBar from '../components/layout/IconBar'
import Sidebar from '../components/chat/Sidebar'
import { driveApi, driveError, type DriveNode, type SortKey } from '../api/drive'
import DriveTable from '../components/drive/DriveTable'
import FolderPickerDialog from '../components/drive/FolderPickerDialog'
import UploadTray, { type UploadItem } from '../components/drive/UploadTray'
import type { MenuItem } from '../components/drive/RowMenu'
import { formatBytes, joinPath } from '../components/drive/driveUtils'

const MAX_PARALLEL_UPLOADS = 3

/** Drive: 개인 파일 공간. 폴더(/drive/:folderId)를 열고, 파일을 올리고 내려받고, 이름 변경·이동·삭제(휴지통)·경로 복사를 한다. */
export default function DrivePage() {
  const { folderId } = useParams()
  const fid = folderId ?? 'root'
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: 'name', desc: false })
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [inlineError, setInlineError] = useState<string | null>(null)
  const [moveIds, setMoveIds] = useState<string[] | null>(null)
  const [moveError, setMoveError] = useState<string | null>(null)
  const [deleteIds, setDeleteIds] = useState<string[] | null>(null)
  const [toast, setToast] = useState<{ text: string; error?: boolean } | null>(null)
  const [dragging, setDragging] = useState(false)
  const dragDepth = useRef(0)
  const fileInput = useRef<HTMLInputElement>(null)

  const say = useCallback((text: string, error = false) => {
    setToast({ text, error })
    window.setTimeout(() => setToast((t) => (t?.text === text ? null : t)), error ? 5000 : 2500)
  }, [])

  const listing = useInfiniteQuery({
    queryKey: ['drive', 'list', fid, sort.key, sort.desc],
    queryFn: ({ pageParam }) => driveApi.list(fid, { sort: sort.key, desc: sort.desc, cursor: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    retry: false,
  })
  const { data: usage } = useQuery({ queryKey: ['drive', 'usage'], queryFn: driveApi.usage, retry: false })
  const first = listing.data?.pages[0]
  const nodes = useMemo(() => listing.data?.pages.flatMap((p) => p.nodes) ?? [], [listing.data])
  const folderPath = first?.path ?? '/'
  const refresh = useCallback(() => qc.invalidateQueries({ queryKey: ['drive'] }), [qc])

  // 폴더를 옮겨 다니면 선택·편집 상태를 비운다
  useEffect(() => { setSelected(new Set()); setRenamingId(null); setCreating(false); setInlineError(null) }, [fid])
  // 목록에서 사라진 항목은 선택에서 뺀다
  useEffect(() => { setSelected((s) => { const ids = new Set(nodes.map((n) => n.id)); const next = new Set([...s].filter((i) => ids.has(i))); return next.size === s.size ? s : next }) }, [nodes])

  // ── 변경 작업 ──
  const createFolder = useMutation({
    mutationFn: (name: string) => driveApi.createFolder(fid, name),
    onSuccess: () => { setCreating(false); setInlineError(null); refresh() },
    onError: (e) => setInlineError(driveError(e, '폴더를 만들지 못했습니다')),
  })
  const rename = useMutation({
    mutationFn: (v: { id: string; name: string }) => driveApi.rename(v.id, v.name),
    onSuccess: () => { setRenamingId(null); setInlineError(null); refresh() },
    onError: (e) => setInlineError(driveError(e, '이름을 바꾸지 못했습니다')),
  })
  const move = useMutation({
    mutationFn: (v: { ids: string[]; parent: string }) => driveApi.move(v.ids, v.parent),
    onSuccess: (r) => { setMoveIds(null); setMoveError(null); setSelected(new Set()); refresh(); say(`${r.moved}개 항목을 이동했습니다`) },
    onError: (e) => setMoveError(driveError(e, '이동하지 못했습니다')),
  })
  const remove = useMutation({
    mutationFn: (ids: string[]) => driveApi.remove(ids),
    onSuccess: (r) => { setDeleteIds(null); setSelected(new Set()); refresh(); say(`${r.trashed}개 항목을 휴지통으로 옮겼습니다`) },
    onError: (e) => { setDeleteIds(null); say(driveError(e, '삭제하지 못했습니다'), true) },
  })

  // ── 업로드 큐 (동시에 MAX_PARALLEL_UPLOADS 개) ──
  // 큐의 원본은 ref 에 두고 화면 상태로 복사해 보여 준다: 상태 갱신 함수 안에서 업로드를 시작하면 개발 모드(Strict Mode)에서 두 번 시작된다.
  const [uploads, setUploads] = useState<UploadItem[]>([])
  const queue = useRef<UploadItem[]>([])
  const jobs = useRef(new Map<string, { file: File; parent: string; abort?: () => void }>())
  const running = useRef(0)
  const sync = useCallback(() => setUploads([...queue.current]), [])
  const patch = useCallback((id: string, p: Partial<UploadItem>) => { queue.current = queue.current.map((x) => (x.id === id ? { ...x, ...p } : x)); sync() }, [sync])
  const drop = useCallback((id: string) => { queue.current = queue.current.filter((x) => x.id !== id); jobs.current.delete(id); sync() }, [sync])

  const pump = useCallback(() => {
    while (running.current < MAX_PARALLEL_UPLOADS) {
      const next = queue.current.find((u) => u.status === 'queued')
      const job = next && jobs.current.get(next.id)
      if (!next || !job) break
      running.current += 1
      patch(next.id, { status: 'uploading', progress: 0 })
      const h = driveApi.upload(job.file, job.parent, (r) => patch(next.id, { progress: r }))
      job.abort = h.abort
      h.promise.then(
        () => { patch(next.id, { status: 'done', progress: 1 }); window.setTimeout(() => drop(next.id), 4000) },
        (e: Error) => { if (e.name === 'AbortError') drop(next.id); else patch(next.id, { status: 'error', error: e.message }) },
      ).finally(() => { running.current -= 1; job.abort = undefined; qc.invalidateQueries({ queryKey: ['drive'] }); pump() })
    }
  }, [patch, drop, qc])

  const enqueue = useCallback((files: File[]) => {
    if (files.length === 0) return
    for (const f of files) {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      jobs.current.set(id, { file: f, parent: fid })
      queue.current.push({ id, name: f.name, progress: 0, status: 'queued' })
    }
    sync()
    pump()
  }, [fid, pump, sync])

  const cancelUpload = (id: string) => {
    const job = jobs.current.get(id)
    if (job?.abort) job.abort()  // 진행 중: 중단되면 onabort 에서 목록에서 빠진다
    else drop(id)
  }
  const retryUpload = (id: string) => { patch(id, { status: 'queued', progress: 0, error: undefined }); pump() }

  // ── 드래그 앤 드롭 ──
  const hasFiles = (e: React.DragEvent) => Array.from(e.dataTransfer.types).includes('Files')
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    dragDepth.current = 0
    setDragging(false)
    const items = Array.from(e.dataTransfer.items ?? [])
    const dirs = items.filter((i) => i.webkitGetAsEntry?.()?.isDirectory).length
    const files = Array.from(e.dataTransfer.files).filter((_, i) => !items[i]?.webkitGetAsEntry?.()?.isDirectory)
    if (dirs > 0) say('폴더는 업로드할 수 없습니다. 파일을 선택해 주세요', true)
    enqueue(files)
  }

  // ── 행 동작 ──
  const toggle = (id: string) => setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n })
  const toggleAll = () => setSelected((s) => (nodes.every((n) => s.has(n.id)) ? new Set() : new Set(nodes.map((n) => n.id))))
  const onSort = (key: SortKey) => setSort((s) => (s.key === key ? { key, desc: !s.desc } : { key, desc: false }))
  const open = (n: DriveNode) => {
    if (n.type === 'folder') navigate(`/drive/${n.id}`)
    else driveApi.download(n).catch((e) => say(driveError(e, '다운로드하지 못했습니다'), true))
  }
  const copyPath = async (n: DriveNode) => {
    try { await navigator.clipboard.writeText(joinPath(folderPath, n.name)); say('경로를 복사했습니다') } catch { say('경로를 복사하지 못했습니다', true) }
  }
  const menuFor = (n: DriveNode): MenuItem[] => [
    { label: '다운로드', onClick: () => open(n), disabled: n.type === 'folder', title: n.type === 'folder' ? '폴더 다운로드는 아직 지원하지 않습니다' : undefined },
    { label: '이름 변경', onClick: () => { setInlineError(null); setRenamingId(n.id) } },
    { label: '이동', onClick: () => { setMoveError(null); setMoveIds([n.id]) } },
    { label: '경로 복사', onClick: () => copyPath(n) },
    { label: '삭제', onClick: () => setDeleteIds([n.id]), danger: true },
  ]

  const crumbs = first?.breadcrumb ?? [{ id: 'root', name: 'Drive' }]
  const deleting = (deleteIds ?? []).map((id) => nodes.find((n) => n.id === id)).filter(Boolean) as DriveNode[]
  const pct = usage ? Math.min(100, (usage.used_bytes / usage.quota_bytes) * 100) : 0

  const headerBtn = 'flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-sm border-none bg-transparent text-content-secondary hover:text-content-primary hover:bg-surface-hover cursor-pointer disabled:opacity-40'

  return (
    <div className="flex h-screen bg-surface-primary overflow-hidden">
      <IconBar />
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-auto relative"
        onDragEnter={(e) => { if (hasFiles(e)) { dragDepth.current += 1; setDragging(true) } }}
        onDragOver={(e) => { if (hasFiles(e)) e.preventDefault() }}
        onDragLeave={() => { dragDepth.current = Math.max(0, dragDepth.current - 1); if (dragDepth.current === 0) setDragging(false) }}
        onDrop={onDrop}>
        <div className="max-w-[860px] mx-auto px-6 pt-10 pb-24">
          <div className="flex items-center gap-2">
            <HardDrive size={20} className="text-content-secondary" aria-hidden />
            <h1 className="flex-1 m-0 text-xl font-semibold text-content-primary">Drive</h1>
            <button onClick={() => { setInlineError(null); setCreating(true) }} className={headerBtn}><FolderPlus size={15} /> 폴더</button>
            <button onClick={() => fileInput.current?.click()} className={headerBtn}><Upload size={15} /> 업로드</button>
            <button onClick={() => navigate('/drive/trash')} title="휴지통" aria-label="휴지통" className={headerBtn}><Trash2 size={15} /></button>
            <button onClick={refresh} title="새로고침" aria-label="새로고침" className={headerBtn}><RefreshCw size={15} className={listing.isFetching ? 'animate-spin' : ''} /></button>
            <input ref={fileInput} type="file" multiple hidden onChange={(e) => { enqueue(Array.from(e.target.files ?? [])); e.target.value = '' }} />
          </div>

          <nav aria-label="경로" className="flex flex-wrap items-center gap-1 mt-5 mb-3 text-sm">
            {crumbs.map((c, i) => (
              <span key={c.id} className="flex items-center gap-1">
                {i > 0 && <ChevronRight size={13} className="text-content-tertiary" aria-hidden />}
                {i === crumbs.length - 1
                  ? <span className="font-semibold text-content-primary" aria-current="page">{c.name}</span>
                  : <button onClick={() => navigate(i === 0 ? '/drive' : `/drive/${c.id}`)} className="border-none bg-transparent p-0 text-sm text-content-secondary hover:text-content-primary cursor-pointer">{c.name}</button>}
              </span>
            ))}
          </nav>

          {selected.size > 0 && (
            <div className="flex items-center gap-2 mb-2 px-3 py-2 rounded-lg bg-accent-primary/10 text-sm" role="toolbar" aria-label="선택한 항목 작업">
              <span className="flex-1 text-content-primary">{selected.size}개 선택됨</span>
              <button onClick={() => { setMoveError(null); setMoveIds([...selected]) }} className={headerBtn}>이동</button>
              <button onClick={() => setDeleteIds([...selected])} className={`${headerBtn} !text-accent-red`}>삭제</button>
              <button onClick={() => setSelected(new Set())} className={headerBtn}>선택 해제</button>
            </div>
          )}

          {listing.isLoading ? (
            <div className="rounded-xl border border-border py-16 flex items-center justify-center text-sm text-content-muted"><Loader2 size={16} className="animate-spin mr-2" /> 불러오는 중...</div>
          ) : listing.isError ? (
            <div role="alert" className="rounded-xl border border-border py-12 text-center text-sm">
              <p className="m-0 mb-3 text-accent-red">{driveError(listing.error, 'Drive 를 불러오지 못했습니다')}</p>
              <button onClick={() => listing.refetch()} className="px-3 py-1.5 rounded-lg text-sm border border-border bg-transparent text-content-primary hover:bg-surface-hover cursor-pointer">다시 시도</button>
            </div>
          ) : (
            <>
              <DriveTable nodes={nodes} selected={selected} onToggle={toggle} onToggleAll={toggleAll} sort={sort} onSort={onSort}
                renamingId={renamingId} renameError={inlineError} onRenameSubmit={(id, name) => rename.mutate({ id, name })} onRenameCancel={() => { setRenamingId(null); setInlineError(null) }}
                creating={creating} createError={inlineError} onCreateSubmit={(name) => createFolder.mutate(name)} onCreateCancel={() => { setCreating(false); setInlineError(null) }}
                onOpen={open} menuFor={menuFor} emptyHint="파일을 끌어다 놓거나 업로드를 누르세요" />
              {listing.hasNextPage && (
                <div className="text-center mt-3">
                  <button onClick={() => listing.fetchNextPage()} disabled={listing.isFetchingNextPage} className="px-3 py-1.5 rounded-lg text-sm border border-border bg-transparent text-content-secondary hover:bg-surface-hover cursor-pointer disabled:opacity-50">
                    {listing.isFetchingNextPage ? '불러오는 중...' : '더 보기'}
                  </button>
                </div>
              )}
            </>
          )}

          {usage && (
            <div className="mt-4 flex items-center gap-3 text-xs text-content-tertiary" aria-label="사용량">
              <div className="w-40 h-1.5 rounded bg-surface-tertiary overflow-hidden" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
                <div className={`h-full ${pct > 90 ? 'bg-accent-red' : 'bg-accent-primary'}`} style={{ width: `${pct}%` }} />
              </div>
              사용량 {formatBytes(usage.used_bytes)} / {formatBytes(usage.quota_bytes)}
            </div>
          )}
        </div>

        {dragging && (
          <div className="pointer-events-none fixed inset-0 z-40 flex items-center justify-center bg-accent-primary/10 border-2 border-dashed border-accent-primary m-3 rounded-2xl">
            <span className="px-4 py-2 rounded-lg bg-surface-primary text-sm text-content-primary shadow">여기에 파일을 놓아 업로드</span>
          </div>
        )}
      </main>

      {moveIds && (
        <FolderPickerDialog title={`${moveIds.length}개 항목 이동`} exclude={moveIds} startId={fid} busy={move.isPending} error={moveError}
          onPick={(parent) => move.mutate({ ids: moveIds, parent })} onClose={() => { setMoveIds(null); setMoveError(null) }} />
      )}

      {deleteIds && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-[18vh] px-4" onMouseDown={() => setDeleteIds(null)}>
          <div role="alertdialog" aria-label="삭제 확인" onMouseDown={(e) => e.stopPropagation()} className="w-full max-w-sm rounded-xl border border-border bg-surface-primary shadow-xl p-5">
            <h2 className="m-0 text-sm font-semibold text-content-primary">{deleting.length === 1 ? `'${deleting[0].name}'` : `${deleteIds.length}개 항목`}을(를) 삭제할까요?</h2>
            <p className="m-0 mt-2 text-xs text-content-secondary leading-relaxed">
              휴지통으로 이동하며 보관 기간이 지나면 영구 삭제됩니다.{deleting.some((n) => n.type === 'folder') && ' 폴더는 안에 있는 모든 항목이 함께 삭제됩니다.'}
            </p>
            <div className="flex justify-end gap-2 mt-4">
              <button autoFocus onClick={() => setDeleteIds(null)} className="px-3 py-1.5 rounded-lg text-sm border border-border bg-transparent text-content-secondary hover:bg-surface-hover cursor-pointer">취소</button>
              <button onClick={() => remove.mutate(deleteIds)} disabled={remove.isPending} className="px-3 py-1.5 rounded-lg text-sm border-none bg-accent-red text-white cursor-pointer disabled:opacity-50 flex items-center gap-1.5">
                {remove.isPending && <Loader2 size={13} className="animate-spin" />} 삭제
              </button>
            </div>
          </div>
        </div>
      )}

      <UploadTray items={uploads} onCancel={cancelUpload} onRetry={retryUpload} onDismiss={drop} />

      {toast && (
        <div role="status" aria-live="polite" className={`fixed left-1/2 -translate-x-1/2 bottom-6 z-50 px-4 py-2 rounded-lg text-sm shadow-lg ${toast.error ? 'bg-accent-red text-white' : 'bg-surface-primary text-content-primary border border-border'}`}>{toast.text}</div>
      )}
    </div>
  )
}

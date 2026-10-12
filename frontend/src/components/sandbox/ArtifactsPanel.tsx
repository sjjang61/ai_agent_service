import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  Archive, ChevronDown, ChevronRight, Download, File, FileText, FolderOpen, Folder, Image as ImageIcon,
  Link2, Loader2, Play, Presentation, RefreshCw, Search,
} from 'lucide-react'
import { sandboxApi } from '../../api/sandbox'
import type { Artifact, ArtifactKind, ArtifactPreview } from '../../types/artifact'

// ─── 유틸 ────────────────────────────────────────────────────────────────────
export function formatSize(n: number) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${(n / 1024 / 1024 / 1024).toFixed(1)} GB`
}

export function relativeTime(iso: string) {
  const sec = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (sec < 60) return '방금'
  if (sec < 3600) return `${Math.floor(sec / 60)}분 전`
  if (sec < 86400) return `${Math.floor(sec / 3600)}시간 전`
  if (sec < 86400 * 30) return `${Math.floor(sec / 86400)}일 전`
  return new Date(iso).toLocaleDateString()
}

function KindIcon({ kind }: { kind: ArtifactKind }) {
  const cls = 'flex-shrink-0'
  switch (kind) {
    case 'image': return <ImageIcon size={13} className={`${cls} text-purple-400`} />
    case 'text': return <FileText size={13} className={`${cls} text-cyan-400`} />
    case 'pdf': return <FileText size={13} className={`${cls} text-red-400`} />
    case 'office': return <Presentation size={13} className={`${cls} text-amber-400`} />
    case 'archive': return <Archive size={13} className={`${cls} text-yellow-500`} />
    default: return <File size={13} className={`${cls} text-slate-500`} />
  }
}

function errorMessage(e: unknown, fallback: string) {
  if (axios.isAxiosError(e)) {
    const d = e.response?.data
    if (typeof d?.detail === 'string') return d.detail
  }
  return fallback
}

async function saveBlob(path: string, name: string) {
  const res = await sandboxApi.fetchArtifactBlob(path, true)
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

// ─── 미리보기 ────────────────────────────────────────────────────────────────
function Preview({ file }: { file: Artifact }) {
  const [preview, setPreview] = useState<ArtifactPreview | null>(null)
  const [imgUrl, setImgUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null
    setPreview(null)
    setImgUrl(null)
    setError(null)
    ;(async () => {
      try {
        if (file.kind === 'image') {
          const res = await sandboxApi.fetchArtifactBlob(file.path, false)
          if (cancelled) return
          objectUrl = URL.createObjectURL(res.data)
          setImgUrl(objectUrl)
          setPreview({ kind: 'image' })
        } else if (file.kind === 'text' || file.kind === 'other') {
          const res = await sandboxApi.previewArtifact(file.path)
          if (!cancelled) setPreview(res.data)
        } else if (!cancelled) {
          setPreview({ kind: 'binary' })
        }
      } catch (e) {
        if (!cancelled) setError(errorMessage(e, '미리보기를 불러오지 못했습니다'))
      }
    })()
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [file.path])

  if (error) return <p className="text-xs text-red-400 px-2 py-2">{error}</p>
  if (!preview) return <p className="text-xs text-slate-500 px-2 py-2">불러오는 중...</p>
  if (preview.kind === 'image' && imgUrl)
    return <img src={imgUrl} alt={file.name} className="max-w-full max-h-72 rounded border border-slate-700 m-2 bg-slate-950" />
  if (preview.kind === 'text')
    return (
      <div className="m-2">
        <pre className="bg-slate-950 rounded-lg p-3 text-xs font-mono overflow-auto max-h-64 text-slate-300 whitespace-pre-wrap break-words border border-slate-700/50">
          {preview.content || '(빈 파일)'}
        </pre>
        {preview.truncated && (
          <p className="text-[10px] text-slate-500 mt-1">앞부분만 표시했습니다 (전체 {formatSize(preview.size)}). 전체는 다운로드하세요.</p>
        )}
      </div>
    )
  return (
    <p className="text-xs text-slate-500 px-2 py-2">
      {preview.kind === 'too_large' ? '파일이 커서 미리보기를 지원하지 않습니다.' : '미리보기를 지원하지 않는 형식입니다.'} 다운로드해서 확인하세요.
    </p>
  )
}

// ─── 트리 ────────────────────────────────────────────────────────────────────
interface Node {
  name: string
  path: string
  files: Artifact[]
  dirs: Map<string, Node>
}

function buildTree(files: Artifact[]): Node {
  const root: Node = { name: '', path: '', files: [], dirs: new Map() }
  for (const f of files) {
    const parts = f.path.split('/')
    let cur = root
    for (let i = 0; i < parts.length - 1; i++) {
      const p = parts.slice(0, i + 1).join('/')
      if (!cur.dirs.has(parts[i])) cur.dirs.set(parts[i], { name: parts[i], path: p, files: [], dirs: new Map() })
      cur = cur.dirs.get(parts[i])!
    }
    cur.files.push(f)
  }
  return root
}

type Sort = 'recent' | 'name' | 'size'
const sorters: Record<Sort, (a: Artifact, b: Artifact) => number> = {
  recent: (a, b) => b.modified.localeCompare(a.modified),
  name: (a, b) => a.name.localeCompare(b.name),
  size: (a, b) => b.size - a.size,
}

function countFiles(n: Node): number {
  let c = n.files.length
  n.dirs.forEach((d) => (c += countFiles(d)))
  return c
}

// ─── 메인 ────────────────────────────────────────────────────────────────────
interface Props {
  /** 채팅 우측 패널 같은 좁은 영역용 */
  compact?: boolean
  /** 값이 바뀌면 목록을 다시 불러온다 (에이전트가 파일을 바꿨을 때) */
  refreshTick?: number
}

export default function ArtifactsPanel({ compact = false, refreshTick = 0 }: Props) {
  const [showHidden, setShowHidden] = useState(false)
  const [filter, setFilter] = useState('')
  const [sort, setSort] = useState<Sort>('recent')
  const [openPath, setOpenPath] = useState<string | null>(null)
  const [closedDirs, setClosedDirs] = useState<Set<string>>(new Set())
  const [notice, setNotice] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)
  const [starting, setStarting] = useState(false)
  const [busyPath, setBusyPath] = useState<string | null>(null)

  const { data, isLoading, isFetching, refetch, error } = useQuery({
    queryKey: ['sandbox-artifacts', showHidden, refreshTick],
    queryFn: async () => (await sandboxApi.getArtifacts(showHidden)).data,
    retry: false,
  })

  const files = data?.files ?? []
  const q = filter.trim().toLowerCase()
  const filtered = useMemo(() => (q ? files.filter((f) => f.path.toLowerCase().includes(q)) : files), [files, q])
  const tree = useMemo(() => buildTree(filtered), [filtered])
  const totalSize = useMemo(() => files.reduce((a, f) => a + f.size, 0), [files])

  const startSandbox = async () => {
    setStarting(true)
    try {
      await sandboxApi.startSandbox()
      await refetch()
    } catch (e) {
      setNotice({ kind: 'error', text: errorMessage(e, 'Sandbox 를 시작하지 못했습니다') })
    } finally {
      setStarting(false)
    }
  }

  const download = async (f: Artifact) => {
    setBusyPath(f.path)
    try {
      await saveBlob(f.path, f.name)
    } catch (e) {
      setNotice({ kind: 'error', text: errorMessage(e, '다운로드하지 못했습니다') })
    } finally {
      setBusyPath(null)
    }
  }

  const publish = async (f: Artifact) => {
    if (!confirm(`'${f.name}' 의 공개 다운로드 링크를 만들까요?\n링크를 아는 사람은 누구나 만료 전까지 내려받을 수 있습니다.`)) return
    setBusyPath(f.path)
    try {
      const res = await sandboxApi.publishArtifact(f.path)
      try {
        await navigator.clipboard.writeText(res.data.url)
        setNotice({ kind: 'ok', text: `링크를 복사했습니다 (만료: ${new Date(res.data.expires_at).toLocaleString()})\n${res.data.url}` })
      } catch {
        setNotice({ kind: 'ok', text: `공개 링크 (만료: ${new Date(res.data.expires_at).toLocaleString()})\n${res.data.url}` })
      }
    } catch (e) {
      setNotice({ kind: 'error', text: errorMessage(e, '링크를 만들지 못했습니다') })
    } finally {
      setBusyPath(null)
    }
  }

  const row = (f: Artifact, depth: number, showPath: boolean) => {
    const open = openPath === f.path
    return (
      <div key={f.path}>
        <div
          className={`group flex items-center gap-1.5 pr-1 rounded text-xs ${open ? 'bg-slate-700/60' : 'hover:bg-slate-800/60'}`}
          style={{ paddingLeft: 8 + depth * 14 }}
        >
          <button onClick={() => setOpenPath(open ? null : f.path)} className="flex-1 min-w-0 flex items-center gap-1.5 py-1 text-left">
            <KindIcon kind={f.kind} />
            <span className="font-mono truncate text-slate-200" title={f.path}>{showPath ? f.path : f.name}</span>
          </button>
          {!compact && <span className="text-slate-500 w-16 text-right flex-shrink-0">{formatSize(f.size)}</span>}
          {!compact && <span className="text-slate-500 w-16 text-right flex-shrink-0">{relativeTime(f.modified)}</span>}
          {compact && <span className="text-slate-600 text-[10px] flex-shrink-0">{formatSize(f.size)}</span>}
          <button onClick={() => download(f)} title="다운로드" className="p-1 text-slate-500 hover:text-slate-200 flex-shrink-0">
            {busyPath === f.path ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
          </button>
          <button onClick={() => publish(f)} title="공개 링크 만들기" className="p-1 text-slate-500 hover:text-slate-200 flex-shrink-0">
            <Link2 size={12} />
          </button>
        </div>
        {open && <Preview file={f} />}
      </div>
    )
  }

  const renderNode = (n: Node, depth: number): React.ReactNode[] => {
    const out: React.ReactNode[] = []
    const dirs = [...n.dirs.values()].sort((a, b) => a.name.localeCompare(b.name))
    for (const d of dirs) {
      const closed = closedDirs.has(d.path)
      out.push(
        <button
          key={`dir:${d.path}`}
          onClick={() => setClosedDirs((s) => { const c = new Set(s); closed ? c.delete(d.path) : c.add(d.path); return c })}
          className="w-full flex items-center gap-1.5 py-1 text-xs text-slate-300 hover:bg-slate-800/60 rounded"
          style={{ paddingLeft: 4 + depth * 14 }}
        >
          {closed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
          {closed ? <Folder size={13} className="text-blue-400" /> : <FolderOpen size={13} className="text-blue-400" />}
          <span className="font-medium">{d.name}</span>
          <span className="text-slate-600">({countFiles(d)})</span>
        </button>
      )
      if (!closed) out.push(...renderNode(d, depth + 1))
    }
    for (const f of [...n.files].sort(sorters[sort])) out.push(row(f, depth + 1, false))
    return out
  }

  const notRunning = data && data.status !== 'running'

  return (
    <div className={compact ? '' : 'bg-slate-800 rounded-xl p-4 border border-slate-700'}>
      <div className="flex items-center justify-between mb-3 gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <FolderOpen size={16} className="text-blue-400 flex-shrink-0" />
          <span className="text-sm font-medium text-white">산출물</span>
          {data?.status === 'running' && (
            <span className="text-xs text-slate-500 truncate">
              {files.length}개 · {formatSize(totalSize)}
            </span>
          )}
        </div>
        <button onClick={() => refetch()} title="새로고침" className="text-slate-400 hover:text-white flex-shrink-0">
          <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />
        </button>
      </div>

      {notice && (
        <div
          className={`mb-3 text-xs rounded-lg px-3 py-2 whitespace-pre-wrap break-all border ${
            notice.kind === 'ok' ? 'bg-green-500/10 border-green-500/30 text-green-300' : 'bg-red-500/10 border-red-500/30 text-red-300'
          }`}
        >
          {notice.text}
          <button onClick={() => setNotice(null)} className="ml-2 underline opacity-70">닫기</button>
        </div>
      )}

      {isLoading ? (
        <p className="text-xs text-slate-500 text-center py-6">불러오는 중...</p>
      ) : error ? (
        <p className="text-xs text-red-400 text-center py-6">{errorMessage(error, '목록을 불러오지 못했습니다')}</p>
      ) : notRunning ? (
        <div className="text-center py-6 space-y-3">
          <p className="text-xs text-slate-400">
            {data.status === 'not_created' ? 'Sandbox 가 아직 만들어지지 않았습니다.' : 'Sandbox 가 중지되어 있습니다.'}
            {data.restorable && ' 시작하면 저장된 백업에서 작업 환경이 복구됩니다.'}
          </p>
          <button
            onClick={startSandbox}
            disabled={starting}
            className="inline-flex items-center gap-2 px-3 py-1.5 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-lg text-xs"
          >
            {starting ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
            {data.restorable ? '시작하고 복구' : '시작'}
          </button>
        </div>
      ) : (
        <>
          <div className="flex items-center gap-2 mb-2">
            <div className="relative flex-1 min-w-0">
              <Search size={12} className="absolute left-2 top-2 text-slate-500" />
              <input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="파일 검색"
                className="w-full pl-7 pr-2 py-1 bg-slate-900 border border-slate-700 rounded text-xs text-white placeholder-slate-600 focus:outline-none focus:border-blue-500"
              />
            </div>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as Sort)}
              className="bg-slate-900 border border-slate-700 rounded text-xs text-slate-300 px-1.5 py-1"
            >
              <option value="recent">최근 수정</option>
              <option value="name">이름</option>
              <option value="size">크기</option>
            </select>
          </div>
          <label className="flex items-center gap-1.5 text-[11px] text-slate-500 mb-2 cursor-pointer">
            <input type="checkbox" checked={showHidden} onChange={(e) => setShowHidden(e.target.checked)} />
            숨김 파일 포함
          </label>

          {filtered.length === 0 ? (
            <p className="text-xs text-slate-500 text-center py-6">{files.length === 0 ? '아직 저장된 파일이 없습니다.' : '검색 결과가 없습니다.'}</p>
          ) : q ? (
            <div className="space-y-0.5">{[...filtered].sort(sorters[sort]).map((f) => row(f, 0, true))}</div>
          ) : (
            <div className="space-y-0.5">{renderNode(tree, -1)}</div>
          )}
          {data?.truncated && <p className="text-[10px] text-slate-500 mt-2">파일이 많아 일부만 표시했습니다.</p>}
        </>
      )}
    </div>
  )
}

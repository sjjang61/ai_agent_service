import { useEffect, useState } from 'react'
import { Download, Loader2, Music } from 'lucide-react'
import { sandboxApi } from '../../api/sandbox'
import type { AgentStepData } from '../../types/chat'

const AUDIO_RE = /[^\s`"'()<>[\]|,]+\.(?:wav|mp3)(?![\w])/gi
const MAX_FILES = 6
const AUTO_LOAD_BYTES = 10 * 1024 * 1024

function mimeOf(path: string): string {
  return path.toLowerCase().endsWith('.mp3') ? 'audio/mpeg' : 'audio/wav'
}

function normalize(raw: string): string | null {
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(raw) && !raw.startsWith('file://')) return null  // 외부 URL 은 대상 아님
  let p = raw.replace(/^file:\/\//, '').replace(/[?#].*$/, '')
  try { p = decodeURIComponent(p) } catch { /* 그대로 */ }
  p = p.replace(/^\/workspace\//, '').replace(/^\.\//, '')
  if (p.startsWith('/') || p.includes('..')) return null  // 작업공간 밖은 무시
  return p
}

/** 답변 본문과 도구 입출력에서 wav/mp3 경로 후보를 모은다 (중복 제거, speech 카드가 이미 보여 주는 것은 제외) */
export function extractAudioPaths(content: string | undefined, steps: AgentStepData[] | undefined, exclude: Set<string>): string[] {
  const texts: string[] = [content ?? '']
  for (const s of steps ?? []) {
    if (s.type === 'tool_call' && s.input != null) texts.push(typeof s.input === 'string' ? s.input : JSON.stringify(s.input))
    if (s.type === 'tool_result' && typeof s.output === 'string' && s.tool !== 'generate_speech') texts.push(s.output)
  }
  const found: string[] = []
  for (const t of texts) {
    for (const m of t.matchAll(AUDIO_RE)) {
      const p = normalize(m[0])
      if (p && !exclude.has(p) && !found.includes(p)) found.push(p)
      if (found.length >= MAX_FILES * 3) break
    }
  }
  return found
}

interface FileInfo { path: string; name: string; size: number }
const listCache = new Map<string, Promise<FileInfo[]>>()

/** 대화의 작업공간 파일 목록을 한 번만 받아 둔다 (실패하면 다음에 다시 시도) */
function loadFiles(conversationId: string): Promise<FileInfo[]> {
  let p = listCache.get(conversationId)
  if (!p) {
    p = sandboxApi.getArtifacts(false, conversationId).then(
      (r) => (r.data.files ?? []).filter((f) => f.kind === 'audio').map((f) => ({ path: f.path, name: f.name, size: f.size })),
    )
    p.catch(() => listCache.delete(conversationId))
    listCache.set(conversationId, p)
    setTimeout(() => listCache.delete(conversationId), 30_000)
  }
  return p
}

function resolve(candidate: string, files: FileInfo[]): FileInfo | null {
  const exact = files.find((f) => f.path === candidate)
  if (exact) return exact
  const base = candidate.split('/').pop()
  const same = files.filter((f) => f.name === base)
  return same.length === 1 ? same[0] : null
}

function fmtSize(b: number): string {
  return b >= 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)}MB` : `${Math.max(1, Math.round(b / 1024))}KB`
}

function Player({ file, conversationId }: { file: FileInfo; conversationId: string }) {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState(false)
  const [wanted, setWanted] = useState(file.size <= AUTO_LOAD_BYTES)
  useEffect(() => {
    if (!wanted) return
    let cancelled = false
    let objectUrl: string | null = null
    setError(false)
    sandboxApi.fetchArtifactBlob(file.path, true, conversationId).then(
      (res) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(new Blob([res.data], { type: mimeOf(file.path) }))
        setUrl(objectUrl)
      },
      () => !cancelled && setError(true),
    )
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [file.path, conversationId, wanted])

  return (
    <div className="flex items-center gap-3 flex-wrap">
      <span className="text-xs text-content-secondary max-w-[220px] truncate" title={file.path}>{file.name}</span>
      <span className="text-[11px] text-content-tertiary w-14">{fmtSize(file.size)}</span>
      {error ? <span role="alert" className="text-xs text-accent-red">오디오를 불러오지 못했습니다</span>
        : !wanted ? <button type="button" onClick={() => setWanted(true)} className="text-xs text-accent-primary hover:underline">불러와서 재생</button>
        : !url ? <span className="flex items-center gap-1.5 text-xs text-content-muted"><Loader2 size={12} className="animate-spin" /> 불러오는 중...</span>
        : <>
            <audio src={url} controls preload="metadata" aria-label={`${file.name} 재생`} className="h-8 flex-1 min-w-[220px] max-w-[420px]" />
            <a href={url} download={file.name} title="다운로드" aria-label={`${file.name} 다운로드`} className="p-1 text-content-tertiary hover:text-content-primary"><Download size={14} /></a>
          </>}
    </div>
  )
}

/** 답변에 나온 wav/mp3 중 작업공간에 실제로 있는 파일만 재생 위젯으로 보여 준다 (없으면 아무것도 그리지 않는다) */
export default function AudioFilesCard({ candidates, conversationId }: { candidates: string[]; conversationId: string }) {
  const [files, setFiles] = useState<FileInfo[]>([])
  const key = candidates.join('\n')
  useEffect(() => {
    if (candidates.length === 0 || !conversationId) { setFiles([]); return }
    let cancelled = false
    loadFiles(conversationId).then(
      (all) => {
        if (cancelled) return
        const out: FileInfo[] = []
        for (const c of candidates) {
          const f = resolve(c, all)
          if (f && !out.some((o) => o.path === f.path)) out.push(f)
        }
        setFiles(out.slice(0, MAX_FILES))
      },
      () => !cancelled && setFiles([]),
    )
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, conversationId])

  if (files.length === 0) return null
  return (
    <section aria-label="오디오 파일" className="my-3 p-3 rounded-xl border border-border bg-surface-secondary space-y-2">
      <div className="flex items-center gap-1.5 text-xs font-medium text-content-secondary"><Music size={14} aria-hidden /> 오디오 파일</div>
      {files.map((f) => <Player key={f.path} file={f} conversationId={conversationId} />)}
    </section>
  )
}

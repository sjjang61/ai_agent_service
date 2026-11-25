import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { browserApi, type BrowserShot } from '../../api/browser'
import { sandboxApi } from '../../api/sandbox'
import { useChatStore } from '../../store/chatStore'
import { useAgentStore } from '../../store/agentStore'

/** 브라우저 작업이 방문한 화면의 스크린샷. 작업 중에는 2초마다 새로 가져온다. */
export function parseBrowserRun(output?: string): string | null {
  return output?.match(/\[browser_run:([0-9a-f]+)\]/)?.[1] ?? null
}

/** 결과 끝의 작업 태그와, 모델에게만 보내는 "[계획 점검]" 안내(서버가 도구 결과에 붙인다)를 화면에서는 가린다 */
export function stripBrowserRun(output: string): string {
  return output.replace(/\n*\[browser_run:[0-9a-f]+\]\s*$/, '').replace(/\n*\[계획 점검\][\s\S]*$/, '')
}

/** 스크린샷 이미지: 로컬 브라우저 것(local://)은 서버 저장소에서, sandbox 브라우저 것은 컨테이너에서 가져온다 */
async function fetchShotUrl(shot: BrowserShot, conversationId: string | null): Promise<string> {
  const blob = shot.path.startsWith('local://')
    ? (await browserApi.shotImage(shot.path.slice('local://'.length))).data
    : (await sandboxApi.fetchArtifactBlob(shot.path, false, conversationId)).data
  return URL.createObjectURL(blob)
}

function Thumb({ shot, conversationId, size, onOpen }: { shot: BrowserShot; conversationId: string | null; size: 'sm' | 'md'; onOpen: () => void }) {
  const { data: src } = useQuery({
    queryKey: ['browser-shot', conversationId, shot.path],
    queryFn: () => fetchShotUrl(shot, conversationId),
    staleTime: Infinity,
    gcTime: 10 * 60 * 1000,
  })
  const host = (() => { try { return new URL(shot.url).hostname } catch { return shot.url } })()
  return (
    <button onClick={onOpen} title={`${shot.title || host}\n${shot.url}`} className={`${size === 'sm' ? 'w-[88px]' : 'w-[calc(50%-4px)]'} flex-shrink-0 text-left bg-transparent border border-border rounded-md overflow-hidden cursor-pointer hover:border-accent-primary p-0`}>
      <div className="bg-surface-tertiary" style={{ aspectRatio: '16 / 10' }}>
        {src && <img src={src} alt={shot.title || host} className="w-full h-full object-cover object-top block" />}
      </div>
      <div className="px-1.5 py-1 text-[10px] text-content-muted truncate">{host}</div>
    </button>
  )
}

interface Props {
  /** 끝난 작업이면 그 작업 id, 진행 중이면 비워 두면 가장 최근 작업 */
  run?: string | null
  running: boolean
  /** sm: 진행 목록 안의 한 줄 미리보기, md: 상세 패널의 격자 */
  size?: 'sm' | 'md'
  /** 채팅 밖(웹사이트 분석 화면 등)에서 쓸 때: 대화 id 와 '실행 중' 여부를 직접 준다 (비우면 채팅 상태를 따른다) */
  conversationId?: string | null
  live?: boolean
}

export default function BrowserShots({ run, running, size = 'md', conversationId: convOverride, live }: Props) {
  const storeConversationId = useChatStore((s) => s.currentConversationId)
  const conversationId = convOverride !== undefined ? convOverride : storeConversationId
  const storeRunning = useAgentStore((s) => s.isRunning)
  const agentRunning = live !== undefined ? live : storeRunning
  const [openPath, setOpenPath] = useState<string | null>(null)
  const { data: shots = [] } = useQuery({
    queryKey: ['browser-shots', conversationId, run ?? 'latest'],
    queryFn: async () => (await browserApi.shots(conversationId, run ?? 'latest')).data,
    refetchInterval: running && agentRunning ? 2000 : false,
    retry: false,
  })
  if (shots.length === 0) return null
  const openIdx = openPath ? shots.findIndex((x) => x.path === openPath) : -1
  const shown = size === 'sm' ? shots.slice(-4) : shots

  return (
    <>
      <div className={size === 'sm' ? 'flex gap-1.5 overflow-x-auto pt-1.5 pb-0.5' : 'flex flex-wrap gap-2'}>
        {shown.map((s) => (
          <Thumb key={s.path} shot={s} conversationId={conversationId} size={size} onOpen={() => setOpenPath(s.path)} />
        ))}
      </div>
      {openIdx >= 0 && (
        <Lightbox
          shot={shots[openIdx]}
          conversationId={conversationId}
          index={openIdx}
          total={shots.length}
          onPrev={openIdx > 0 ? () => setOpenPath(shots[openIdx - 1].path) : undefined}
          onNext={openIdx < shots.length - 1 ? () => setOpenPath(shots[openIdx + 1].path) : undefined}
          onClose={() => setOpenPath(null)}
        />
      )}
    </>
  )
}

function Lightbox({ shot, conversationId, index, total, onPrev, onNext, onClose }: {
  shot: BrowserShot; conversationId: string | null; index: number; total: number
  onPrev?: () => void; onNext?: () => void; onClose: () => void
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft' && onPrev) onPrev()
      else if (e.key === 'ArrowRight' && onNext) onNext()
      else if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onPrev, onNext, onClose])
  const arrow = 'absolute top-1/2 -translate-y-1/2 z-10 w-10 h-10 rounded-full bg-black/60 hover:bg-black/80 text-white flex items-center justify-center border-none cursor-pointer'
  const { data: src } = useQuery({
    queryKey: ['browser-shot', conversationId, shot.path],
    queryFn: () => fetchShotUrl(shot, conversationId),
    staleTime: Infinity,
  })
  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-6" onClick={onClose}>
      {onPrev && <button onClick={(e) => { e.stopPropagation(); onPrev() }} aria-label="이전 스크린샷" className={`${arrow} left-4`}><ChevronLeft size={22} /></button>}
      {onNext && <button onClick={(e) => { e.stopPropagation(); onNext() }} aria-label="다음 스크린샷" className={`${arrow} right-4`}><ChevronRight size={22} /></button>}
      <div className="bg-surface-primary rounded-xl border border-border max-w-[1100px] w-full max-h-full overflow-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 px-4 py-2 border-b border-border">
          <div className="min-w-0 flex-1">
            <div className="text-sm text-content-primary truncate">{shot.title || shot.url}</div>
            <a href={shot.url} target="_blank" rel="noopener noreferrer" className="text-xs text-accent-primary truncate block">{shot.url}</a>
          </div>
          {total > 1 && <span className="text-xs text-content-muted flex-shrink-0">{index + 1} / {total}</span>}
          <button onClick={onClose} aria-label="닫기" className="p-1.5 text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer"><X size={16} /></button>
        </div>
        {src && <img src={src} alt={shot.title} className="w-full block" />}
      </div>
    </div>
  )
}

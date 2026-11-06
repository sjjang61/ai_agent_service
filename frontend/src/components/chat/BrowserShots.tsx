import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { browserApi, type BrowserShot } from '../../api/browser'
import { sandboxApi } from '../../api/sandbox'
import { useChatStore } from '../../store/chatStore'
import { useAgentStore } from '../../store/agentStore'

/** 브라우저 작업이 방문한 화면의 스크린샷. 작업 중에는 2초마다 새로 가져온다. */
export function parseBrowserRun(output?: string): string | null {
  return output?.match(/\[browser_run:([0-9a-f]+)\]/)?.[1] ?? null
}

export function stripBrowserRun(output: string): string {
  return output.replace(/\n*\[browser_run:[0-9a-f]+\]\s*$/, '')
}

function Thumb({ shot, conversationId, size, onOpen }: { shot: BrowserShot; conversationId: string | null; size: 'sm' | 'md'; onOpen: () => void }) {
  const { data: src } = useQuery({
    queryKey: ['browser-shot', conversationId, shot.path],
    queryFn: async () => URL.createObjectURL((await sandboxApi.fetchArtifactBlob(shot.path, false, conversationId)).data),
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
}

export default function BrowserShots({ run, running, size = 'md' }: Props) {
  const conversationId = useChatStore((s) => s.currentConversationId)
  const agentRunning = useAgentStore((s) => s.isRunning)
  const [open, setOpen] = useState<BrowserShot | null>(null)
  const { data: shots = [] } = useQuery({
    queryKey: ['browser-shots', conversationId, run ?? 'latest'],
    queryFn: async () => (await browserApi.shots(conversationId, run ?? 'latest')).data,
    refetchInterval: running && agentRunning ? 2000 : false,
    retry: false,
  })
  if (shots.length === 0) return null
  const shown = size === 'sm' ? shots.slice(-4) : shots

  return (
    <>
      <div className={size === 'sm' ? 'flex gap-1.5 overflow-x-auto pt-1.5 pb-0.5' : 'flex flex-wrap gap-2'}>
        {shown.map((s) => (
          <Thumb key={s.path} shot={s} conversationId={conversationId} size={size} onOpen={() => setOpen(s)} />
        ))}
      </div>
      {open && <Lightbox shot={open} conversationId={conversationId} onClose={() => setOpen(null)} />}
    </>
  )
}

function Lightbox({ shot, conversationId, onClose }: { shot: BrowserShot; conversationId: string | null; onClose: () => void }) {
  const { data: src } = useQuery({
    queryKey: ['browser-shot', conversationId, shot.path],
    queryFn: async () => URL.createObjectURL((await sandboxApi.fetchArtifactBlob(shot.path, false, conversationId)).data),
    staleTime: Infinity,
  })
  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-6" onClick={onClose}>
      <div className="bg-surface-primary rounded-xl border border-border max-w-[1100px] w-full max-h-full overflow-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 px-4 py-2 border-b border-border">
          <div className="min-w-0 flex-1">
            <div className="text-sm text-content-primary truncate">{shot.title || shot.url}</div>
            <a href={shot.url} target="_blank" rel="noopener noreferrer" className="text-xs text-accent-primary truncate block">{shot.url}</a>
          </div>
          <button onClick={onClose} aria-label="닫기" className="p-1.5 text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer"><X size={16} /></button>
        </div>
        {src && <img src={src} alt={shot.title} className="w-full block" />}
      </div>
    </div>
  )
}

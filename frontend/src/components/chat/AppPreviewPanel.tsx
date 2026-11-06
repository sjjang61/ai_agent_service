import { useEffect, useState } from 'react'
import { ExternalLink, Loader2, RefreshCw } from 'lucide-react'

/**
 * 웹앱을 iframe 으로 보여 준다. 접속 주소는 열 때마다 launch() 로 새로 받는다
 * (비공개 앱의 실행 티켓은 60초짜리 일회용이라 같은 주소를 다시 쓸 수 없다).
 * 컨테이너가 꺼져 있었다면 앱의 '시작 중' 화면이 보였다가 준비되면 스스로 새로고침된다.
 */
export default function AppPreviewPanel({ name, launch }: { name: string; launch: () => Promise<string> }) {
  const [nonce, setNonce] = useState(0)
  const [url, setUrl] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setUrl(null)
    setErr(null)
    launch().then(
      (u) => !cancelled && setUrl(u),
      (e) => !cancelled && setErr((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? '앱을 열지 못했습니다'),
    )
    return () => { cancelled = true }
    // launch 는 호출하는 쪽에서 앱마다 새로 만들어지므로 nonce 로만 다시 연다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce])

  // 새 창은 티켓이 일회용이라 iframe 이 쓴 주소를 재사용할 수 없다: 새로 받아 연다 (팝업 차단을 피하려 창을 먼저 연다)
  const openNew = async () => {
    const w = window.open('', '_blank')
    try {
      const u = await launch()
      if (w) w.location.href = u
    } catch {
      w?.close()
    }
  }
  const shown = url?.replace(/\?t=[^&]*/, '') ?? ''

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-1.5 px-3 py-2 border-b border-border bg-surface-secondary">
        <span className="flex-1 min-w-0 truncate text-xs text-content-secondary" title={shown}>{shown || name}</span>
        <button onClick={() => setNonce((n) => n + 1)} title="새로고침" aria-label="새로고침" className="p-1.5 text-content-muted hover:text-content-primary border-none bg-transparent cursor-pointer"><RefreshCw size={13} /></button>
        <button onClick={openNew} title="새 창에서 열기" aria-label="새 창에서 열기" className="p-1.5 text-content-muted hover:text-content-primary border-none bg-transparent cursor-pointer"><ExternalLink size={13} /></button>
      </div>
      {err ? (
        <div className="flex-1 flex items-center justify-center text-sm text-accent-red px-6 text-center">{err}</div>
      ) : !url ? (
        <div className="flex-1 flex items-center justify-center text-sm text-content-muted"><Loader2 size={16} className="animate-spin mr-2" /> 여는 중...</div>
      ) : (
        <iframe
          key={`${url}`}
          src={url}
          title={name}
          className="flex-1 w-full border-0 bg-white"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals allow-downloads"
          referrerPolicy="no-referrer"
        />
      )}
    </div>
  )
}

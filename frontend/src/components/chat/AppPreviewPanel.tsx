import { useEffect, useRef, useState } from 'react'
import { ExternalLink, Loader2, RefreshCw, Terminal } from 'lucide-react'

/**
 * 웹앱을 iframe 으로 보여 준다. 접속 주소는 열 때마다 launch() 로 새로 받는다
 * (비공개 앱의 실행 티켓은 60초짜리 일회용이라 같은 주소를 다시 쓸 수 없다).
 * 컨테이너가 꺼져 있었다면 앱의 '시작 중' 화면이 보였다가 준비되면 스스로 새로고침된다.
 * logs 를 주면(내 앱만) 새로고침 오른쪽에 서버 로그 터미널 버튼이 생긴다. 남의 앱(스토어·검수)에는 주지 않는다.
 */
// 터미널 색 이스케이프(ANSI)는 화면에서 글자로 보이므로 지운다
// eslint-disable-next-line no-control-regex
const ANSI = /\x1b\[[0-9;?]*[ -/]*[@-~]/g

function LogTerminal({ logs, onClose }: { logs: () => Promise<string>; onClose: () => void }) {
  const [text, setText] = useState('')
  const [err, setErr] = useState(false)
  const [follow, setFollow] = useState(true)
  const box = useRef<HTMLPreElement>(null)

  useEffect(() => {
    let stop = false
    const pull = () => logs().then((t) => { if (!stop) { setText(t.replace(ANSI, '')); setErr(false) } }, () => !stop && setErr(true))
    pull()
    const id = setInterval(pull, 3000)
    return () => { stop = true; clearInterval(id) }
    // logs 는 호출하는 쪽에서 매번 새로 만들어지므로 한 번만 연결한다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const el = box.current
    if (follow && el) el.scrollTop = el.scrollHeight
  }, [text, follow])

  return (
    <div className="h-56 shrink-0 flex flex-col border-t border-border bg-[#0d1117]" aria-label="서버 로그">
      <div className="flex items-center gap-2 px-3 py-1 text-[11px] text-[#8b949e] border-b border-[#21262d]">
        <Terminal size={12} /> <span className="flex-1">서버 로그{err && ' (불러오지 못했습니다)'}</span>
        <label className="flex items-center gap-1 cursor-pointer"><input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} /> 자동 스크롤</label>
        <button onClick={onClose} className="px-1 border-none bg-transparent text-[#8b949e] hover:text-white cursor-pointer" aria-label="로그 닫기">닫기</button>
      </div>
      <pre ref={box} className="flex-1 m-0 p-3 overflow-auto text-[11px] leading-relaxed text-[#c9d1d9] font-mono whitespace-pre-wrap break-all">
        {text.trim() ? text : '아직 출력된 로그가 없습니다'}
      </pre>
    </div>
  )
}

export default function AppPreviewPanel({ name, launch, logs }: { name: string; launch: () => Promise<string>; logs?: () => Promise<string> }) {
  const [showLogs, setShowLogs] = useState(false)
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
        {logs && (
          <button onClick={() => setShowLogs((v) => !v)} title="서버 로그" aria-label="서버 로그" aria-pressed={showLogs}
            className={`p-1.5 border-none bg-transparent cursor-pointer ${showLogs ? 'text-accent-blue' : 'text-content-muted hover:text-content-primary'}`}><Terminal size={13} /></button>
        )}
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
      {logs && showLogs && <LogTerminal logs={logs} onClose={() => setShowLogs(false)} />}
    </div>
  )
}

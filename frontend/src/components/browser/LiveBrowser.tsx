import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, Loader2, RotateCw, X } from 'lucide-react'
import { useAuthStore } from '../../store/authStore'

const VIEW_W = 1280
const VIEW_H = 800
const SPECIAL_KEYS = new Set([
  'Enter', 'Backspace', 'Tab', 'Escape', 'Delete', 'Home', 'End', 'PageUp', 'PageDown',
  'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight',
])

interface Props {
  /** 대화방 sandbox 의 브라우저를 쓴다. 비어 있으면 사용자 공용 sandbox */
  conversationId?: string
  initialUrl?: string
  doneLabel: string
  /** 로그인 상태를 저장한 뒤 호출 */
  onDone: () => void
  onClose: () => void
  /** 보조 버튼(예: 취소) */
  extra?: React.ReactNode
}

/** sandbox 브라우저를 화면에 띄워 사용자가 직접 로그인하게 하는 창. 입력은 브라우저로만 전달되고 에이전트(LLM)에는 노출되지 않는다. */
export default function LiveBrowser({ conversationId, initialUrl, doneLabel, onDone, onClose, extra }: Props) {
  const token = useAuthStore((s) => s.token)
  const wsRef = useRef<WebSocket | null>(null)
  const imgRef = useRef<HTMLImageElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const flushTimer = useRef<number | undefined>(undefined)
  const composing = useRef(false)
  const doneRef = useRef(onDone)
  doneRef.current = onDone
  const [status, setStatus] = useState<'connecting' | 'ready' | 'error'>('connecting')
  const [message, setMessage] = useState('')
  const [frame, setFrame] = useState<string | null>(null)
  const [pageUrl, setPageUrl] = useState('')
  const [addr, setAddr] = useState('')
  const [saving, setSaving] = useState(false)

  const send = useCallback((obj: Record<string, unknown>) => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj))
  }, [])

  useEffect(() => {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const q = new URLSearchParams({ token: token ?? '' })
    if (conversationId) q.set('conversation_id', conversationId)
    // 개발 서버(vite)의 WebSocket 프록시가 불안정해, 기존 채팅 WebSocket 처럼 개발 중에는 백엔드(8500)에 직접 연결한다
    const host = location.port === "5173" ? `${location.hostname}:8500` : location.host
    const ws = new WebSocket(`${proto}//${host}/ws/browser/live?${q}`)
    wsRef.current = ws
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data)
      if (m.t === 'ready') {
        setStatus('ready')
        if (initialUrl) ws.send(JSON.stringify({ t: 'goto', url: initialUrl }))
      } else if (m.t === 'frame') {
        setFrame(m.img)
        setPageUrl(m.url)
        setAddr((a) => (document.activeElement?.id === 'live-addr' ? a : m.url))
      } else if (m.t === 'saved') {
        doneRef.current()
      } else if (m.t === 'notice') {
        setMessage(m.message)
      } else if (m.t === 'error') {
        setStatus('error')
        setMessage(m.message)
      }
    }
    ws.onclose = (e) => setStatus((s) => (s === 'ready' || s === 'connecting' ? (e.code === 1000 ? s : 'error') : s))
    ws.onerror = () => setMessage('연결에 실패했습니다')
    return () => {
      window.clearTimeout(flushTimer.current)
      ws.close()
    }
    // 연결은 한 번만 만든다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const flushText = () => {
    const ta = inputRef.current
    if (ta && ta.value) {
      send({ t: 'text', text: ta.value })
      ta.value = ''
    }
  }
  const scheduleFlush = () => {
    window.clearTimeout(flushTimer.current)
    flushTimer.current = window.setTimeout(flushText, 50)
  }

  const toViewport = (e: { clientX: number; clientY: number }) => {
    const r = imgRef.current!.getBoundingClientRect()
    return { x: ((e.clientX - r.left) * VIEW_W) / r.width, y: ((e.clientY - r.top) * VIEW_H) / r.height }
  }

  const finish = () => {
    setSaving(true)
    send({ t: 'save' })
    window.setTimeout(() => setSaving(false), 10000) // 응답이 없으면 버튼을 다시 연다
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="bg-surface-primary border border-border rounded-xl shadow-xl w-full max-w-[1100px] max-h-full flex flex-col overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-border">
          <button onClick={() => send({ t: 'back' })} title="뒤로" className="p-1.5 text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer"><ArrowLeft size={15} /></button>
          <button onClick={() => send({ t: 'reload' })} title="새로고침" className="p-1.5 text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer"><RotateCw size={14} /></button>
          <input
            id="live-addr"
            value={addr}
            onChange={(e) => setAddr(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') send({ t: 'goto', url: addr }) }}
            placeholder="주소를 입력하세요"
            className="flex-1 px-3 py-1.5 bg-surface-secondary border border-border rounded-md text-sm text-content-primary focus:outline-none focus:border-accent-primary"
          />
          <button onClick={onClose} title="닫기" className="p-1.5 text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer"><X size={16} /></button>
        </div>

        <div className="relative bg-black/5 overflow-auto flex-1 min-h-[300px]">
          {frame ? (
            <div className="relative cursor-pointer" onClick={() => inputRef.current?.focus()}>
              <img
                ref={imgRef}
                src={`data:image/jpeg;base64,${frame}`}
                alt={pageUrl}
                draggable={false}
                className="w-full block select-none"
                style={{ aspectRatio: `${VIEW_W} / ${VIEW_H}` }}
                onClick={(e) => { inputRef.current?.focus(); send({ t: 'click', ...toViewport(e) }) }}
                onDoubleClick={(e) => send({ t: 'click', ...toViewport(e), count: 2 })}
                onContextMenu={(e) => { e.preventDefault(); send({ t: 'click', ...toViewport(e), button: 'right' }) }}
                onWheel={(e) => send({ t: 'wheel', ...toViewport(e), dy: e.deltaY })}
              />
              <textarea
                ref={inputRef}
                aria-label="브라우저 입력"
                autoFocus
                className="absolute left-0 top-0 w-px h-px opacity-0 pointer-events-none"
                onInput={() => { if (!composing.current) scheduleFlush() }}
                onCompositionStart={() => { composing.current = true }}
                onCompositionEnd={() => { composing.current = false; scheduleFlush() }}
                onKeyDown={(e) => {
                  if (composing.current || e.nativeEvent.isComposing) return
                  const mod = e.ctrlKey || e.metaKey
                  if (SPECIAL_KEYS.has(e.key) || (mod && e.key.length === 1 && !['v', 'c', 'x'].includes(e.key.toLowerCase()))) {
                    e.preventDefault()
                    window.clearTimeout(flushTimer.current)
                    flushText()
                    send({ t: 'key', key: `${mod ? 'Control+' : ''}${e.shiftKey && SPECIAL_KEYS.has(e.key) ? 'Shift+' : ''}${e.key}` })
                  }
                }}
              />
            </div>
          ) : (
            <div className="h-[400px] flex flex-col items-center justify-center gap-2 text-sm text-content-muted">
              {status === 'error' ? <span className="text-accent-red">{message || '브라우저에 연결하지 못했습니다'}</span> : (<><Loader2 size={18} className="animate-spin" />브라우저를 여는 중...</>)}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 px-4 py-3 border-t border-border">
          <p className="text-xs text-content-muted flex-1 min-w-0">
            {message && status !== 'error' ? message : '화면을 클릭해 직접 로그인하세요. 입력한 비밀번호는 에이전트에 전달되지 않습니다.'}
          </p>
          {extra}
          <button
            disabled={saving || status !== 'ready'}
            onClick={finish}
            className="px-4 py-2 bg-accent-primary hover:bg-accent-primary/90 disabled:opacity-50 text-white rounded-md text-sm font-medium border-none cursor-pointer disabled:cursor-not-allowed"
          >
            {saving ? '저장 중...' : doneLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

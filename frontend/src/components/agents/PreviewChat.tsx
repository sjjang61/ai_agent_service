import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'
import { RotateCcw, Send, Square } from 'lucide-react'
import { chatApi } from '../../api/chat'
import { useAuthStore } from '../../store/authStore'
import type { AgentConfig } from '../../types/customAgent'

interface Step { tool: string; done: boolean }
interface Msg { role: 'user' | 'assistant'; content: string; steps: Step[]; error?: string }

interface Props {
  agentId: string
  config: AgentConfig // 저장하지 않은 편집 내용으로 실행한다
  starters: string[]
}

/** 빌더 미리보기: 초안(저장 전 편집 내용 포함)으로 실행해 본다. 대화는 목록에 나타나지 않는 테스트 대화로 만들어진다. */
export default function PreviewChat({ agentId, config, starters }: Props) {
  const token = useAuthStore((s) => s.token)
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [running, setRunning] = useState(false)
  const convRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ block: 'end' }) }, [messages])
  useEffect(() => () => abortRef.current?.abort(), [])
  useEffect(() => { convRef.current = null; setMessages([]) }, [agentId]) // 다른 에이전트로 바뀌면 새 대화

  const patchLast = (fn: (m: Msg) => Msg) =>
    setMessages((ms) => ms.map((m, i) => (i === ms.length - 1 ? fn(m) : m)))

  const send = async (text: string) => {
    const content = text.trim()
    if (!content || running) return
    setInput('')
    setRunning(true)
    setMessages((ms) => [...ms, { role: 'user', content, steps: [] }, { role: 'assistant', content: '', steps: [] }])
    const controller = new AbortController()
    abortRef.current = controller
    try {
      if (!convRef.current) {
        const res = await chatApi.createConversation({ title: '미리보기', agent_id: agentId, is_test: true })
        convRef.current = res.data.id as string
      }
      const cid = convRef.current
      const resp = await fetch(`/api/chat/conversations/${cid}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ content, agent_config: config, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone }),
        signal: controller.signal,
      })
      if (!resp.ok || !resp.body) {
        let detail = '실행하지 못했습니다.'
        try { const b = await resp.json(); if (typeof b?.detail === 'string') detail = b.detail } catch { /* JSON 이 아님 */ }
        patchLast((m) => ({ ...m, error: detail }))
        return
      }
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? '' // 청크 경계에서 잘린 줄은 다음 읽기에서 이어 붙인다
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          let ev: { type: string; content?: string; tool?: string; message?: string }
          try { ev = JSON.parse(line.slice(6)) } catch { continue }
          if (ev.type === 'token' && ev.content) patchLast((m) => ({ ...m, content: m.content + ev.content }))
          else if (ev.type === 'tool_call' && ev.tool) {
            patchLast((m) => ({ ...m, steps: [...m.steps, { tool: ev.tool!, done: false }] }))
            if (ev.tool === 'form_ask_user') {
              // 미리보기는 질문 폼을 그리지 않으므로 취소해 대기하지 않게 한다
              chatApi.answerForm(cid, { cancelled: true }).catch(() => undefined)
            }
          } else if (ev.type === 'tool_result' && ev.tool) {
            patchLast((m) => {
              const idx = [...m.steps].reverse().findIndex((s) => s.tool === ev.tool && !s.done)
              if (idx < 0) return m
              const real = m.steps.length - 1 - idx
              return { ...m, steps: m.steps.map((s, i) => (i === real ? { ...s, done: true } : s)) }
            })
          } else if (ev.type === 'error') patchLast((m) => ({ ...m, error: ev.message || '실행 중 오류가 발생했습니다.' }))
          else if (ev.type === 'done') setRunning(false)
        }
      }
    } catch (e) {
      if ((e as Error)?.name !== 'AbortError') patchLast((m) => ({ ...m, error: '연결이 끊어졌습니다.' }))
    } finally {
      setRunning(false)
    }
  }

  const stop = async () => {
    if (convRef.current) await chatApi.cancelRun(convRef.current).catch(() => abortRef.current?.abort())
  }
  const reset = () => {
    abortRef.current?.abort()
    convRef.current = null
    setMessages([])
    setRunning(false)
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center justify-between px-4 h-11 border-b border-border flex-shrink-0">
        <span className="text-[13px] font-medium text-content-primary">미리보기</span>
        <button onClick={reset} title="새 대화로 다시 시작" aria-label="새 대화로 다시 시작" className="flex items-center gap-1 text-xs text-content-tertiary hover:text-content-primary border-none bg-transparent cursor-pointer">
          <RotateCcw size={13} /> 초기화
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-sm text-content-muted pt-10 space-y-3">
            <p>저장하지 않은 편집 내용으로 바로 실행해 볼 수 있습니다.</p>
            {starters.filter(Boolean).map((s) => (
              <button key={s} onClick={() => send(s)} className="block mx-auto max-w-full px-3 py-1.5 rounded-full text-[13px] border border-border text-content-secondary hover:bg-surface-hover cursor-pointer bg-transparent truncate">{s}</button>
            ))}
          </div>
        )}
        {messages.map((m, i) =>
          m.role === 'user' ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[85%] px-3.5 py-2 rounded-[var(--radius-lg)] bg-accent-primary text-white text-[14px] whitespace-pre-wrap">{m.content}</div>
            </div>
          ) : (
            <div key={i} className="space-y-1.5">
              {m.steps.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {m.steps.map((s, k) => (
                    <span key={k} className={`text-[11px] px-2 py-0.5 rounded-full border ${s.done ? 'border-border text-content-tertiary' : 'border-accent-primary/50 text-accent-primary'}`}>
                      {s.done ? '✓' : '…'} {s.tool}
                    </span>
                  ))}
                </div>
              )}
              {m.content && (
                <div className="text-[14px] text-content-primary leading-relaxed [&_p]:my-1.5 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_pre]:bg-surface-tertiary [&_pre]:p-2 [&_pre]:rounded [&_pre]:overflow-x-auto [&_code]:text-[13px] [&_a]:text-accent-primary">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>{m.content}</ReactMarkdown>
                </div>
              )}
              {m.error && <p className="text-[13px] text-accent-red">⚠️ {m.error}</p>}
              {running && i === messages.length - 1 && !m.content && !m.error && (
                <div role="status" className="thinking-indicator flex items-center gap-2 text-[13px] text-content-secondary">
                  <span className="thinking-dots" aria-hidden><span /><span /><span /></span>
                  {m.steps.some((s) => !s.done) ? `${m.steps.filter((s) => !s.done).slice(-1)[0].tool} 실행 중…` : '생각하는 중…'}
                </div>
              )}
            </div>
          )
        )}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={(e) => { e.preventDefault(); void send(input) }} className="p-3 border-t border-border flex gap-2 flex-shrink-0">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(input) } }}
          rows={2}
          placeholder="메시지를 입력하세요 (Shift+Enter: 줄바꿈)"
          aria-label="미리보기 메시지"
          className="flex-1 resize-none px-3 py-2 rounded-[var(--radius-md)] bg-surface-secondary border border-border text-[14px] text-content-primary placeholder:text-content-muted focus:outline-none focus:border-accent-primary"
        />
        {running ? (
          <button type="button" onClick={stop} aria-label="중지" className="w-10 h-10 self-end rounded-full bg-accent-red text-white flex items-center justify-center border-none cursor-pointer"><Square size={14} /></button>
        ) : (
          <button type="submit" disabled={!input.trim()} aria-label="전송" className="w-10 h-10 self-end rounded-full bg-accent-primary text-white flex items-center justify-center border-none cursor-pointer disabled:opacity-40"><Send size={15} /></button>
        )}
      </form>
    </div>
  )
}

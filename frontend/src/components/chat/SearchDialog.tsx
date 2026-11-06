import { Fragment, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2, MessageSquare, Search, X } from 'lucide-react'
import { chatApi } from '../../api/chat'
import { formatMonthDay } from '../../utils/time'
import type { SearchResult } from '../../types/chat'

/** 검색어와 일치하는 부분을 강조한다 (대소문자 무시) */
function Highlight({ text, q }: { text: string; q: string }) {
  const needle = q.trim()
  if (!needle) return <>{text}</>
  const lower = text.toLowerCase()
  const n = needle.toLowerCase()
  const out: React.ReactNode[] = []
  let from = 0
  for (let i = lower.indexOf(n); i >= 0; i = lower.indexOf(n, from)) {
    if (i > from) out.push(text.slice(from, i))
    out.push(<mark key={i} className="bg-accent-primary/25 text-content-primary rounded-sm px-0.5">{text.slice(i, i + n.length)}</mark>)
    from = i + n.length
  }
  out.push(text.slice(from))
  return <>{out.map((x, i) => <Fragment key={i}>{x}</Fragment>)}</>
}

/** 대화방 검색: 제목과 메시지 내용에서 찾아 보여 주고, 선택하면 그 대화방으로 이동한다. ↑↓ 로 고르고 Enter 로 열 수 있다. */
export default function SearchDialog({ onSelect, onClose }: { onSelect: (conversationId: string) => void; onClose: () => void }) {
  const [input, setInput] = useState('')
  const [q, setQ] = useState('')
  const [active, setActive] = useState(0)
  const listRef = useRef<HTMLUListElement>(null)

  // 입력이 멈추면 검색한다
  useEffect(() => {
    const t = window.setTimeout(() => setQ(input.trim()), 300)
    return () => window.clearTimeout(t)
  }, [input])

  const { data = [], isFetching, isError } = useQuery<SearchResult[]>({
    queryKey: ['chat-search', q],
    queryFn: async () => (await chatApi.search(q)).data,
    enabled: q.length > 0,
    staleTime: 30_000,
    retry: false,
  })
  const results = q ? data : []

  useEffect(() => setActive(0), [q])
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-idx="${active}"]`)?.scrollIntoView({ block: 'nearest' })
  }, [active])

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') onClose()
    else if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => Math.min(i + 1, results.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter' && results[active] && !e.nativeEvent.isComposing) onSelect(results[active].conversation_id)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-[12vh] px-4" onMouseDown={onClose}>
      <div
        className="w-full max-w-[640px] max-h-[70vh] flex flex-col bg-surface-primary border border-border rounded-[var(--radius-xl)] shadow-xl overflow-hidden"
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="대화 검색"
      >
        <div className="flex items-center gap-2.5 px-4 py-3 border-b border-border">
          <Search size={16} className="text-content-muted flex-shrink-0" />
          <input
            autoFocus
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="대화 제목과 내용 검색"
            className="flex-1 bg-transparent border-none outline-none text-sm text-content-primary placeholder-content-muted"
          />
          {isFetching && <Loader2 size={14} className="animate-spin text-content-muted" />}
          <button onClick={onClose} aria-label="닫기" className="text-content-tertiary hover:text-content-primary border-none bg-transparent cursor-pointer"><X size={16} /></button>
        </div>

        <ul ref={listRef} className="flex-1 overflow-y-auto py-1">
          {!q ? (
            <li className="px-4 py-8 text-center text-xs text-content-muted">검색어를 입력하면 내 대화방의 제목과 메시지 내용에서 찾습니다.</li>
          ) : isError ? (
            <li className="px-4 py-8 text-center text-xs text-accent-red">검색하지 못했습니다. 잠시 후 다시 시도해 주세요.</li>
          ) : results.length === 0 && !isFetching ? (
            <li className="px-4 py-8 text-center text-xs text-content-muted">'{q}' 와 일치하는 대화가 없습니다.</li>
          ) : (
            results.map((r, i) => (
              <li key={r.conversation_id} data-idx={i}>
                <button
                  onClick={() => onSelect(r.conversation_id)}
                  onMouseEnter={() => setActive(i)}
                  className={`w-full text-left px-4 py-2.5 border-none cursor-pointer ${i === active ? 'bg-surface-active' : 'bg-transparent hover:bg-surface-hover'}`}
                >
                  <div className="flex items-center gap-2">
                    <MessageSquare size={13} className="flex-shrink-0 text-content-muted" />
                    <span className="flex-1 min-w-0 truncate text-sm font-medium text-content-primary"><Highlight text={r.title} q={q} /></span>
                    {r.updated_at && <span className="flex-shrink-0 text-[11px] text-content-muted">{formatMonthDay(r.updated_at)}</span>}
                  </div>
                  {r.snippets.map((s) => (
                    <div key={s.message_id} className="mt-1 pl-[21px] text-xs text-content-secondary line-clamp-2">
                      <span className="text-content-muted mr-1.5">{s.role === 'user' ? '나' : 'Agent'}</span>
                      <Highlight text={s.text} q={q} />
                    </div>
                  ))}
                </button>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  )
}

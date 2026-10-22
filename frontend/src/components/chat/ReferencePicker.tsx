import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileText, MessageSquare, Search, X, Check } from 'lucide-react'
import { spacesApi } from '../../api/spaces'
import { useChatStore } from '../../store/chatStore'
import type { Reference } from '../../types/chat'
import type { PageSummary } from '../../types/space'

export const MAX_REFERENCES = 5

interface Props {
  selected: Reference[]
  currentConversationId: string
  onChange: (refs: Reference[]) => void
  onClose: () => void
}

/** 스페이스 페이지·이전 대화를 검색해 질문에 참조 자료로 붙이는 대화상자 */
export default function ReferencePicker({ selected, currentConversationId, onChange, onClose }: Props) {
  const [tab, setTab] = useState<'page' | 'conversation'>('page')
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const conversations = useChatStore((s) => s.conversations)

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 250)
    return () => clearTimeout(t)
  }, [query])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const { data: pages = [], isLoading } = useQuery<PageSummary[]>({
    queryKey: ['reference-pages', debounced],
    queryFn: async () => (await spacesApi.listPages({ view: 'all', q: debounced || undefined })).data,
    enabled: tab === 'page',
  })

  const convs = useMemo(() => {
    const q = query.trim().toLowerCase()
    return conversations.filter((c) => c.id !== currentConversationId && (!q || (c.title ?? '').toLowerCase().includes(q)))
  }, [conversations, currentConversationId, query])

  const isSelected = (type: Reference['type'], id: string) => selected.some((r) => r.type === type && r.id === id)
  const full = selected.length >= MAX_REFERENCES

  const toggle = (ref: Reference) => {
    if (isSelected(ref.type, ref.id)) onChange(selected.filter((r) => !(r.type === ref.type && r.id === ref.id)))
    else if (!full) onChange([...selected, ref])
  }

  const rows: { ref: Reference; sub?: string }[] =
    tab === 'page'
      ? pages.map((p) => ({ ref: { type: 'page', id: p.id, title: p.title || '제목 없음' }, sub: p.snippet }))
      : convs.map((c) => ({ ref: { type: 'conversation', id: c.id, title: c.title || '새 대화' } }))

  const tabCls = (on: boolean) =>
    `px-3 py-1.5 rounded-full text-[13px] border-none cursor-pointer ${on ? 'bg-surface-active text-content-primary' : 'bg-transparent text-content-secondary hover:bg-surface-hover'}`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-label="참조 추가"
        onMouseDown={(e) => e.stopPropagation()}
        className="w-[520px] max-w-[92vw] max-h-[70vh] flex flex-col bg-surface-secondary border border-border rounded-[var(--radius-lg)] shadow-xl"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h3 className="text-[15px] font-semibold text-content-primary">참조 추가</h3>
          <button onClick={onClose} aria-label="닫기" className="p-1 text-content-muted hover:text-content-primary border-none bg-transparent cursor-pointer">
            <X size={16} />
          </button>
        </div>
        <div className="px-4 pt-3 flex items-center gap-2">
          <button className={tabCls(tab === 'page')} onClick={() => setTab('page')}>스페이스 페이지</button>
          <button className={tabCls(tab === 'conversation')} onClick={() => setTab('conversation')}>이전 대화</button>
          <span className="ml-auto text-xs text-content-muted">{selected.length} / {MAX_REFERENCES}</span>
        </div>
        <div className="px-4 py-3">
          <div className="flex items-center gap-2 px-3 py-2 rounded-[var(--radius-md)] bg-surface-tertiary border border-border">
            <Search size={14} className="text-content-muted" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={tab === 'page' ? '페이지 검색' : '대화 검색'}
              className="flex-1 bg-transparent outline-none text-sm text-content-primary placeholder:text-content-muted"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-3 min-h-[160px]">
          {tab === 'page' && isLoading ? (
            <div className="py-8 text-center text-sm text-content-tertiary">불러오는 중...</div>
          ) : rows.length === 0 ? (
            <div className="py-8 text-center text-sm text-content-muted">검색 결과가 없습니다.</div>
          ) : (
            rows.map(({ ref, sub }) => {
              const on = isSelected(ref.type, ref.id)
              const disabled = !on && full
              return (
                <button
                  key={`${ref.type}:${ref.id}`}
                  onClick={() => toggle(ref)}
                  disabled={disabled}
                  className="w-full flex items-start gap-2.5 px-3 py-2 rounded-[var(--radius-md)] text-left border-none bg-transparent cursor-pointer hover:bg-surface-hover disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {ref.type === 'page' ? <FileText size={15} className="mt-0.5 text-cyan-400 flex-shrink-0" /> : <MessageSquare size={15} className="mt-0.5 text-accent-primary flex-shrink-0" />}
                  <span className="flex-1 min-w-0">
                    <span className="block text-sm text-content-primary truncate">{ref.title}</span>
                    {sub && <span className="block text-xs text-content-muted truncate">{sub}</span>}
                  </span>
                  {on && <Check size={15} className="mt-0.5 text-accent-primary flex-shrink-0" />}
                </button>
              )
            })
          )}
        </div>
        <div className="flex justify-end px-4 py-3 border-t border-border">
          <button onClick={onClose} className="px-4 py-1.5 rounded-[var(--radius-md)] text-sm bg-accent-primary text-white border-none cursor-pointer hover:bg-accent-hover">
            완료
          </button>
        </div>
      </div>
    </div>
  )
}

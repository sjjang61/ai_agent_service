import { useState, useMemo, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Search, Trash2, Edit2, BookOpen, ChevronDown, ChevronRight, ListTree, ShieldCheck, RefreshCw, Link2 } from 'lucide-react'
import { useWikiEntries, useDeleteWikiEntry, useWikiLint } from '../../hooks/useWiki'
import { useWikiStore } from '../../store/wikiStore'
import WikiForm from './WikiForm'
import WikiMarkdown from './WikiMarkdown'
import { T } from '../skills/typography'
import type { WikiEntry, WikiCategory, WikiLintType } from '../../types/wiki'

const CATEGORY_LABELS: Record<WikiCategory, { label: string; color: string }> = {
  general: {
    label: '일반',
    color: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
  },
  work: {
    label: '업무',
    color: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  },
  learning: {
    label: '학습',
    color: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  },
  reference: {
    label: '참고',
    color: 'bg-green-500/20 text-green-400 border-green-500/30',
  },
}

const LINT_LABELS: Record<WikiLintType, string> = {
  duplicate: '중복 가능성',
  stale: '오래된 문서',
  orphan: '연결 없는 문서',
  broken_link: '깨진 연결',
  no_summary: '요약 없음',
}

type View = 'list' | 'index' | 'lint'

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  if (isNaN(date.getTime())) return ''
  const month = date.getMonth() + 1
  const day = date.getDate()
  return `${month}월 ${day}일`
}

/** addTick: 페이지 제목 줄의 '새 항목' 버튼을 누를 때마다 바뀌는 값. 바뀌면 입력 폼을 연다. */
export default function WikiList({ addTick = 0 }: { addTick?: number }) {
  const {
    entries,
    selectedCategory,
    searchQuery,
    setSelectedCategory,
    setSearchQuery,
  } = useWikiStore()

  const queryParams = useMemo(
    () => ({
      category: selectedCategory || undefined,
      query: searchQuery || undefined,
      limit: 200,
    }),
    [selectedCategory, searchQuery]
  )

  const { isLoading, refetch } = useWikiEntries(queryParams)
  const deleteMutation = useDeleteWikiEntry()

  const [showForm, setShowForm] = useState(false)
  const [editEntry, setEditEntry] = useState<WikiEntry | null>(null)

  useEffect(() => {
    if (addTick > 0) {
      setEditEntry(null)
      setShowForm(true)
    }
  }, [addTick])
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [view, setView] = useState<View>('list')
  const [tagFilter, setTagFilter] = useState<string | null>(null)
  const lint = useWikiLint(view === 'lint')
  const docs = useMemo(() => entries.map((e) => ({ id: e.id, title: e.title })), [entries])

  /** 다른 문서로 이동: 목록 보기로 바꾸고 그 문서를 펼쳐 화면에 보이게 한다 */
  const openEntry = (id: string) => {
    setView('list')
    setSelectedCategory(null)
    setSearchQuery('')
    setExpandedId(id)
  }

  useEffect(() => {
    if (view === 'list' && expandedId) {
      document.getElementById(`wiki-${expandedId}`)?.scrollIntoView({ block: 'start', behavior: 'smooth' })
    }
  }, [view, expandedId])

  const handleDelete = async (id: string) => {
    if (!confirm('이 Wiki 항목을 삭제하시겠습니까?')) return
    await deleteMutation.mutateAsync(id)
  }

  const categories: (WikiCategory | null)[] = [null, 'general', 'work', 'learning', 'reference']

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="flex gap-1" role="tablist" aria-label="위키 보기">
          {([['list', '목록', BookOpen], ['index', '인덱스', ListTree], ['lint', '점검', ShieldCheck]] as const).map(([key, label, Icon]) => (
            <button
              key={key}
              role="tab"
              aria-selected={view === key}
              onClick={() => setView(key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm border-none cursor-pointer transition-colors ${
                view === key ? 'bg-surface-active text-content-primary' : 'bg-transparent text-content-secondary hover:bg-surface-hover'
              }`}
            >
              <Icon size={14} /> {label}
            </button>
          ))}
        </div>
      </div>

      {/* Search & Filter */}
      {view === 'list' && (
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-content-secondary"
          />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="검색..."
            className="w-full pl-9 pr-3 py-2 bg-surface-secondary border border-border rounded-[var(--radius-md)] text-content-primary text-sm focus:outline-none focus:border-accent-primary"
          />
        </div>

        <div className="flex gap-2">
          {categories.map((cat) => (
            <button
              key={cat || 'all'}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-2 rounded-[var(--radius-md)] text-sm transition-colors border ${
                selectedCategory === cat
                  ? 'bg-accent-primary text-white border-accent-primary'
                  : 'bg-surface-secondary text-content-secondary border-border hover:bg-surface-tertiary'
              }`}
            >
              {cat ? CATEGORY_LABELS[cat].label : '전체'}
            </button>
          ))}
        </div>
      </div>

      )}

      {/* Form */}
      {showForm && (
        <WikiForm
          entry={editEntry}
          onClose={() => {
            setShowForm(false)
            setEditEntry(null)
          }}
        />
      )}

      {view === 'index' && <WikiIndex entries={entries} tagFilter={tagFilter} onTag={setTagFilter} onOpen={openEntry} />}

      {view === 'lint' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs text-content-tertiary">
              {lint.data ? `문서 ${lint.data.total}개를 점검했습니다. 문제 ${lint.data.issues.length}건` : '점검 중…'}
            </p>
            <button onClick={() => lint.refetch()} className="flex items-center gap-1 text-xs text-accent-primary bg-transparent border-none cursor-pointer">
              <RefreshCw size={12} className={lint.isFetching ? 'animate-spin' : ''} /> 다시 점검
            </button>
          </div>
          {lint.data && lint.data.issues.length === 0 && (
            <div className="text-center py-10 text-content-secondary text-sm border border-dashed border-border rounded-[var(--radius-lg)]">문제가 없습니다.</div>
          )}
          {(Object.keys(LINT_LABELS) as WikiLintType[]).map((type) => {
            const items = lint.data?.issues.filter((i) => i.type === type) ?? []
            if (!items.length) return null
            return (
              <div key={type} className="rounded-[var(--radius-lg)] border border-border bg-surface-secondary p-3">
                <h4 className={`${T.section} mb-2`}>{LINT_LABELS[type]} <span className="font-normal text-content-tertiary">{items.length}</span></h4>
                <ul className="space-y-1.5">
                  {items.map((it, i) => (
                    <li key={i} className="text-[13px] text-content-secondary flex flex-wrap items-center gap-x-2 gap-y-1">
                      {it.entries.map((en) => (
                        <button key={en.id} onClick={() => openEntry(en.id)} className="text-accent-primary hover:underline bg-transparent border-none cursor-pointer p-0">{en.title}</button>
                      ))}
                      <span className="text-content-tertiary">— {it.message}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </div>
      )}

      {/* List */}
      {view === 'list' && (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 items-start">
        {isLoading ? (
          <p className="col-span-full text-center text-content-secondary py-8">로딩중...</p>
        ) : entries.length === 0 ? (
          <div className="col-span-full text-center py-12 text-content-secondary">
            <BookOpen size={48} className="mx-auto mb-3 opacity-30" />
            <p>저장된 Wiki 항목이 없습니다</p>
            <p className="text-sm mt-1">채팅 응답에서 텍스트를 선택하여 저장하세요</p>
          </div>
        ) : (
          entries.map((entry) => {
            const isExpanded = expandedId === entry.id
            return (
              <div
                key={entry.id}
                id={`wiki-${entry.id}`}
                className={`scroll-mt-4 ${isExpanded ? 'lg:col-span-2' : ''} p-4 bg-surface-secondary border border-border rounded-[var(--radius-md)] hover:bg-surface-tertiary transition-colors`}
              >
                <div
                  className="flex items-start justify-between cursor-pointer"
                  onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      {isExpanded ? (
                        <ChevronDown size={16} className="text-content-secondary" />
                      ) : (
                        <ChevronRight size={16} className="text-content-secondary" />
                      )}
                      <h3 className={T.itemTitle}>{entry.title}</h3>
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs border ${
                          CATEGORY_LABELS[entry.category].color
                        }`}
                      >
                        {CATEGORY_LABELS[entry.category].label}
                      </span>
                    </div>
                    <div className="ml-6 flex items-center gap-3 text-xs text-content-secondary">
                      <span>{formatDate(entry.created_at)}</span>
                      {entry.tags.length > 0 && (
                        <div className="flex gap-1">
                          {entry.tags.map((tag) => (
                            <span key={tag} className="text-accent-primary">
                              #{tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => {
                        setEditEntry(entry)
                        setShowForm(true)
                      }}
                      className="p-1.5 text-content-secondary hover:text-accent-primary transition-colors"
                    >
                      <Edit2 size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(entry.id)}
                      className="p-1.5 text-content-secondary hover:text-accent-red transition-colors"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="ml-6 mt-3 pt-3 border-t border-border">
                    {entry.summary && (
                      <p className="mb-3 px-3 py-2 rounded-[var(--radius-md)] bg-accent-primary/10 border border-accent-primary/20 text-[13px] text-content-primary">
                        {entry.summary}
                      </p>
                    )}
                    <WikiMarkdown docs={docs} onOpen={openEntry}>{entry.content}</WikiMarkdown>
                    {((entry.links?.length ?? 0) > 0 || (entry.backlinks?.length ?? 0) > 0) && (
                      <div className="mt-3 space-y-1.5 text-xs">
                        {(entry.links?.length ?? 0) > 0 && <LinkRow label="연결한 문서" refs={entry.links!} onOpen={openEntry} />}
                        {(entry.backlinks?.length ?? 0) > 0 && <LinkRow label="이 문서를 참조하는 문서" refs={entry.backlinks!} onOpen={openEntry} />}
                      </div>
                    )}
                    {(entry.source_text || entry.source_conversation_id) && (
                      <div className="mt-3 pt-2 border-t border-border/60 flex flex-wrap items-start gap-x-4 gap-y-1 text-xs text-content-tertiary">
                        {entry.source_conversation_id && (
                          <Link to={`/chat/${entry.source_conversation_id}`} className="text-accent-primary hover:underline">
                            출처 대화 열기
                          </Link>
                        )}
                        {entry.source_text && (
                          <details className="w-full">
                            <summary className="cursor-pointer hover:text-content-primary">정리 전 원문 보기</summary>
                            <p className="mt-1.5 px-3 py-2 bg-surface-tertiary rounded-[var(--radius-md)] whitespace-pre-wrap text-content-secondary">
                              {entry.source_text}
                            </p>
                          </details>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>
      )}
    </div>
  )
}

function LinkRow({ label, refs, onOpen }: { label: string; refs: { id: string; title: string }[]; onOpen: (id: string) => void }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="flex items-center gap-1 text-content-tertiary"><Link2 size={11} /> {label}</span>
      {refs.map((r) => (
        <button key={r.id} onClick={() => onOpen(r.id)} className="px-2 py-0.5 rounded-full border border-border bg-surface-tertiary text-accent-primary hover:bg-surface-hover cursor-pointer">
          {r.title}
        </button>
      ))}
    </div>
  )
}

/** 인덱스: 카테고리별 목차. 제목·요약·태그·참조 수를 한눈에 보고, 태그로 좁히고, 눌러서 문서를 연다. */
function WikiIndex({ entries, tagFilter, onTag, onOpen }: { entries: WikiEntry[]; tagFilter: string | null; onTag: (t: string | null) => void; onOpen: (id: string) => void }) {
  const tags = useMemo(() => {
    const count = new Map<string, number>()
    entries.forEach((e) => (e.tags ?? []).forEach((t) => count.set(t, (count.get(t) ?? 0) + 1)))
    return [...count.entries()].sort((a, b) => b[1] - a[1]).slice(0, 24)
  }, [entries])
  const order: WikiCategory[] = ['general', 'work', 'learning', 'reference']
  const shown = tagFilter ? entries.filter((e) => (e.tags ?? []).includes(tagFilter)) : entries
  if (entries.length === 0) return <div className="text-center py-12 text-content-secondary text-sm">저장된 Wiki 항목이 없습니다</div>
  return (
    <div className="space-y-4">
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5" aria-label="태그">
          {tags.map(([t, n]) => (
            <button
              key={t}
              onClick={() => onTag(tagFilter === t ? null : t)}
              className={`px-2.5 py-1 rounded-full text-xs border cursor-pointer ${tagFilter === t ? 'bg-accent-primary text-white border-accent-primary' : 'bg-surface-secondary text-content-secondary border-border hover:bg-surface-hover'}`}
            >
              #{t} <span className="opacity-60">{n}</span>
            </button>
          ))}
        </div>
      )}
      {order.map((cat) => {
        const list = shown.filter((e) => e.category === cat).sort((a, b) => a.title.localeCompare(b.title, 'ko'))
        if (!list.length) return null
        return (
          <section key={cat}>
            <h3 className={`${T.section} mb-2`}>
              {CATEGORY_LABELS[cat].label} <span className="font-normal text-content-tertiary">{list.length}</span>
            </h3>
            <ul className="rounded-[var(--radius-lg)] border border-border bg-surface-secondary divide-y divide-border">
              {list.map((e) => (
                <li key={e.id}>
                  <button onClick={() => onOpen(e.id)} className="w-full text-left px-4 py-2.5 bg-transparent border-none cursor-pointer hover:bg-surface-hover">
                    <div className="flex items-center gap-2">
                      <span className={T.itemTitle}>{e.title}</span>
                      {(e.backlinks?.length ?? 0) > 0 && <span className="text-[11px] text-content-tertiary">참조 {e.backlinks!.length}</span>}
                    </div>
                    {e.summary && <div className="text-xs text-content-secondary truncate">{e.summary}</div>}
                    {(e.tags ?? []).length > 0 && <div className="text-[11px] text-accent-primary mt-0.5">{e.tags.map((t) => `#${t}`).join(' ')}</div>}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )
      })}
    </div>
  )
}

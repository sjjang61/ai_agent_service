import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, FileText, LayoutGrid, List, MessageSquare, RotateCcw, Search, Star, Trash2 } from 'lucide-react'
import SpacesLayout from '../components/spaces/SpacesLayout'
import { TEMPLATES, type PageTemplate } from '../components/spaces/templates'
import { relativeTime } from '../components/spaces/utils'
import { spacesApi } from '../api/spaces'
import { chatApi } from '../api/chat'
import { useChatStore } from '../store/chatStore'
import type { Conversation } from '../types/chat'
import type { PageDetail, PageSummary, Space } from '../types/space'

type Tab = 'recommended' | 'favorites' | 'mine'
const TABS: { key: Tab; label: string }[] = [
  { key: 'recommended', label: '추천' },
  { key: 'favorites', label: '즐겨찾기' },
  { key: 'mine', label: '내 항목' },
]

function loadMode(): 'list' | 'grid' {
  try {
    return localStorage.getItem('spaces-view-mode') === 'grid' ? 'grid' : 'list'
  } catch {
    return 'list'
  }
}

export default function SpacesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [params] = useSearchParams()
  const spaceId = params.get('space')
  const trash = params.get('view') === 'trash'

  const [tab, setTab] = useState<Tab>('recommended')
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [mode, setMode] = useState<'list' | 'grid'>(loadMode)
  const [menu, setMenu] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 250)
    return () => clearTimeout(t)
  }, [query])
  useEffect(() => {
    const close = (e: MouseEvent) => menuRef.current && !menuRef.current.contains(e.target as Node) && setMenu(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const view = trash ? 'trash' : tab === 'favorites' ? 'favorites' : 'all'
  const { data: pages = [], isLoading } = useQuery<PageSummary[]>({
    queryKey: ['pages', { view, space_id: spaceId, q: debounced }],
    queryFn: async () =>
      (await spacesApi.listPages({ view, space_id: spaceId ?? undefined, q: debounced || undefined })).data,
  })
  const { data: spaces = [] } = useQuery<Space[]>({
    queryKey: ['spaces'],
    queryFn: async () => (await spacesApi.listSpaces()).data,
  })
  const spaceName = spaces.find((s) => s.id === spaceId)?.name
  const addConversation = useChatStore((s) => s.addConversation)

  /** 이 스페이스에서 대화 시작: 공용 sandbox 를 쓰는 대화방을 만들고 채팅 화면으로 이동한다 */
  const startChat = useMutation({
    mutationFn: async () =>
      (await chatApi.createConversation({ title: spaceName ? `${spaceName} 작업` : 'New Conversation', space_id: spaceId ?? undefined })).data as Conversation,
    onSuccess: (c) => {
      addConversation(c)
      navigate(`/chat/${c.id}`)
    },
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['pages'] })
    queryClient.invalidateQueries({ queryKey: ['spaces'] })
  }

  const createPage = useMutation({
    mutationFn: async (t?: PageTemplate) =>
      (await spacesApi.createPage({ title: t?.title ?? '', content: t?.content ?? '', space_id: spaceId })).data as PageDetail,
    onSuccess: (p) => {
      refresh()
      navigate(`/spaces/pages/${p.id}`)
    },
  })

  const toggleFav = async (p: PageSummary) => {
    await spacesApi.updatePage(p.id, { is_favorite: !p.is_favorite })
    refresh()
  }
  const toTrash = async (p: PageSummary) => {
    await spacesApi.trashPage(p.id)
    refresh()
  }
  const restore = async (p: PageSummary) => {
    await spacesApi.restorePage(p.id)
    refresh()
  }
  const purge = async (p: PageSummary) => {
    if (!confirm(`'${p.title || '제목 없음'}' 을(를) 영구 삭제할까요? 되돌릴 수 없습니다.`)) return
    await spacesApi.deletePermanently(p.id)
    refresh()
  }
  const emptyTrash = async () => {
    if (!confirm('휴지통을 비울까요? 되돌릴 수 없습니다.')) return
    await spacesApi.emptyTrash()
    refresh()
  }
  const setViewMode = (m: 'list' | 'grid') => {
    setMode(m)
    try { localStorage.setItem('spaces-view-mode', m) } catch { /* 저장 불가 환경은 무시 */ }
  }

  const title = trash ? '휴지통' : spaceName ?? '전체'
  const iconBtn = (active: boolean) =>
    `w-9 h-9 flex items-center justify-center rounded-full border-none cursor-pointer ${active ? 'bg-surface-active text-content-primary' : 'bg-transparent text-content-tertiary hover:bg-surface-hover'}`

  const actions = (p: PageSummary) =>
    trash ? (
      <>
        <button onClick={(e) => { e.stopPropagation(); restore(p) }} title="복원" aria-label="복원" className="text-content-tertiary hover:text-accent-primary border-none bg-transparent cursor-pointer"><RotateCcw size={15} /></button>
        <button onClick={(e) => { e.stopPropagation(); purge(p) }} title="영구 삭제" aria-label="영구 삭제" className="text-content-tertiary hover:text-accent-red border-none bg-transparent cursor-pointer"><Trash2 size={15} /></button>
      </>
    ) : (
      <>
        <button onClick={(e) => { e.stopPropagation(); toggleFav(p) }} title="즐겨찾기" aria-label="즐겨찾기" aria-pressed={p.is_favorite} className={`border-none bg-transparent cursor-pointer ${p.is_favorite ? 'text-accent-yellow' : 'text-content-tertiary hover:text-accent-yellow'}`}>
          <Star size={15} fill={p.is_favorite ? 'currentColor' : 'none'} />
        </button>
        <button onClick={(e) => { e.stopPropagation(); toTrash(p) }} title="휴지통으로 이동" aria-label="휴지통으로 이동" className="text-content-tertiary hover:text-accent-red border-none bg-transparent cursor-pointer"><Trash2 size={15} /></button>
      </>
    )

  const open = (p: PageSummary) => !trash && navigate(`/spaces/pages/${p.id}`)

  return (
    <SpacesLayout>
      <div className="px-10 pt-8 pb-4 flex-shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-[28px] font-semibold text-content-primary flex-1 truncate">{title}</h1>
          <div className="flex items-center gap-2 w-[300px] px-3.5 py-2 border border-border rounded-full bg-surface-primary focus-within:border-accent-primary">
            <Search size={15} className="text-content-tertiary" />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="검색" className="flex-1 bg-transparent border-none outline-none text-[13px] text-content-primary placeholder:text-content-muted" />
          </div>
          {!trash && spaceId && (
            <button
              onClick={() => startChat.mutate()}
              disabled={startChat.isPending}
              title="이 스페이스의 공용 sandbox 에서 에이전트와 작업합니다"
              className="flex items-center gap-1.5 px-4 py-2.5 rounded-full border border-border text-[14px] text-content-primary bg-transparent cursor-pointer hover:bg-surface-hover disabled:opacity-50"
            >
              <MessageSquare size={15} /> AI 와 작업
            </button>
          )}
          {trash ? (
            <button onClick={emptyTrash} disabled={pages.length === 0} className="px-4 py-2 rounded-full border border-border text-[14px] text-content-primary bg-transparent cursor-pointer hover:bg-surface-hover disabled:opacity-40 disabled:cursor-not-allowed">
              휴지통 비우기
            </button>
          ) : (
            <div className="relative" ref={menuRef}>
              <button onClick={() => setMenu((m) => !m)} className="flex items-center gap-1.5 px-5 py-2.5 rounded-full bg-content-primary text-surface-primary text-[14px] font-medium border-none cursor-pointer hover:opacity-90">
                새로 만들기 <ChevronDown size={15} />
              </button>
              {menu && (
                <div className="absolute right-0 mt-2 w-[240px] z-40 bg-surface-primary border border-border rounded-[var(--radius-lg)] shadow-xl p-1.5">
                  <button onClick={() => { setMenu(false); createPage.mutate(undefined) }} className="w-full flex items-center gap-2.5 text-left px-3 py-2 rounded-[var(--radius-md)] hover:bg-surface-hover border-none bg-transparent cursor-pointer text-[13px] text-content-primary">
                    <FileText size={15} /> 빈 페이지
                  </button>
                  <div className="px-3 pt-2 pb-1 text-xs text-content-tertiary">템플릿</div>
                  {TEMPLATES.map((t) => (
                    <button key={t.key} onClick={() => { setMenu(false); createPage.mutate(t) }} className="w-full flex items-center gap-2.5 text-left px-3 py-2 rounded-[var(--radius-md)] hover:bg-surface-hover border-none bg-transparent cursor-pointer text-[13px] text-content-primary">
                      <t.icon size={15} style={{ color: t.color }} /> {t.title}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {!trash && (
          <div className="flex items-center mt-6">
            <div className="flex items-center gap-1 flex-1">
              {TABS.map((t) => (
                <button key={t.key} onClick={() => setTab(t.key)} className={`px-5 py-2 rounded-full text-[14px] border-none cursor-pointer ${tab === t.key ? 'bg-surface-active text-content-primary' : 'bg-transparent text-content-secondary hover:bg-surface-hover'}`}>
                  {t.label}
                </button>
              ))}
            </div>
            <button onClick={() => setViewMode('grid')} className={iconBtn(mode === 'grid')} title="격자 보기" aria-label="격자 보기"><LayoutGrid size={16} /></button>
            <button onClick={() => setViewMode('list')} className={iconBtn(mode === 'list')} title="목록 보기" aria-label="목록 보기"><List size={16} /></button>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-10 pb-10">
        {!trash && tab === 'recommended' && !debounced && (
          <section className="mb-8">
            <h2 className="text-[18px] font-semibold text-content-primary">Space에서 페이지 작성하기</h2>
            <p className="text-[14px] text-content-secondary mt-1 mb-4">템플릿을 선택해 에이전트와 함께 작업을 시작하세요.</p>
            <div className="flex gap-3 overflow-x-auto pb-2">
              {TEMPLATES.map((t) => (
                <button
                  key={t.key}
                  onClick={() => createPage.mutate(t)}
                  disabled={createPage.isPending}
                  className="w-[200px] flex-shrink-0 h-[110px] p-4 flex flex-col justify-between text-left rounded-[var(--radius-lg)] border border-border bg-surface-secondary hover:border-accent-primary hover:bg-surface-hover transition-colors cursor-pointer"
                >
                  <t.icon size={22} style={{ color: t.color }} />
                  <span className="text-[14px] text-content-primary">{t.title}</span>
                </button>
              ))}
            </div>
          </section>
        )}

        {isLoading ? (
          <div className="text-content-tertiary text-sm py-12 text-center">불러오는 중...</div>
        ) : pages.length === 0 ? (
          <div className="text-content-muted text-sm py-12 text-center">
            {debounced ? '검색 결과가 없습니다.' : trash ? '휴지통이 비어 있습니다.' : tab === 'favorites' ? '즐겨찾기한 페이지가 없습니다.' : '페이지가 없습니다. "새로 만들기"로 시작하세요.'}
          </div>
        ) : mode === 'list' || trash ? (
          <table className="w-full text-left">
            <thead>
              <tr className="text-[13px] text-content-tertiary border-b border-border">
                <th className="font-normal py-3 px-3">이름</th>
                <th className="font-normal py-3 px-3 w-[160px]">{trash ? '삭제됨' : '최근 활동'}</th>
                <th className="w-[80px]" />
              </tr>
            </thead>
            <tbody>
              {pages.map((p) => (
                <tr key={p.id} onClick={() => open(p)} className={`group border-b border-border hover:bg-surface-hover ${trash ? '' : 'cursor-pointer'}`}>
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="w-9 h-9 rounded-[var(--radius-md)] border border-border flex items-center justify-center text-accent-primary flex-shrink-0"><FileText size={16} /></span>
                      <div className="min-w-0">
                        <div className="text-[14px] text-content-primary truncate">
                          {p.title || '제목 없음'}
                          {p.space_id && <span className="ml-2 text-xs text-content-tertiary">{spaces.find((s) => s.id === p.space_id)?.name}</span>}
                        </div>
                        {p.snippet && <div className="text-xs text-content-tertiary truncate max-w-[520px]">{p.snippet}</div>}
                      </div>
                    </div>
                  </td>
                  <td className="py-3 px-3 text-[14px] text-content-secondary">{relativeTime(trash && p.deleted_at ? p.deleted_at : p.updated_at)}</td>
                  <td className="py-3 px-3"><div className="flex items-center gap-3 justify-end opacity-0 group-hover:opacity-100 focus-within:opacity-100">{actions(p)}</div></td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {pages.map((p) => (
              <div key={p.id} onClick={() => open(p)} className="group relative h-[150px] p-4 rounded-[var(--radius-lg)] border border-border bg-surface-secondary hover:border-accent-primary cursor-pointer flex flex-col">
                <div className="text-[14px] font-medium text-content-primary truncate">{p.title || '제목 없음'}</div>
                <div className="text-xs text-content-tertiary mt-1 line-clamp-3 flex-1">{p.snippet}</div>
                <div className="text-xs text-content-tertiary">{relativeTime(p.updated_at)}</div>
                <div className="absolute top-3 right-3 flex gap-2 opacity-0 group-hover:opacity-100 focus-within:opacity-100">{actions(p)}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </SpacesLayout>
  )
}

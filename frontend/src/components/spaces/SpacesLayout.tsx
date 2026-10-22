import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, FilePlus2, FileText, Folder, Library, Plus, Search, Trash2, X } from 'lucide-react'
import IconBar from '../layout/IconBar'
import { spacesApi } from '../../api/spaces'
import type { PageDetail, PageSummary, Space } from '../../types/space'

interface Props {
  children: React.ReactNode
  /** 편집기에서는 현재 페이지를 '최근' 목록에서 강조 */
  currentPageId?: string
}

/** 스페이스 공통 레이아웃: 아이콘 바 + 보조 사이드바(새 페이지/전체/최근/공간/휴지통) + 본문 */
export default function SpacesLayout({ children, currentPageId }: Props) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [params] = useSearchParams()
  const spaceId = params.get('space')
  const view = params.get('view')
  const [filter, setFilter] = useState('')
  const [searching, setSearching] = useState(false)
  const [adding, setAdding] = useState(false)
  const [newSpace, setNewSpace] = useState('')

  const { data: spaces = [] } = useQuery<Space[]>({
    queryKey: ['spaces'],
    queryFn: async () => (await spacesApi.listSpaces()).data,
  })
  const { data: pages = [] } = useQuery<PageSummary[]>({
    queryKey: ['pages', { view: 'all' }],
    queryFn: async () => (await spacesApi.listPages({ view: 'all' })).data,
  })

  const create = useMutation({
    mutationFn: async () => (await spacesApi.createPage({ space_id: spaceId })).data as PageDetail,
    onSuccess: (p) => {
      queryClient.invalidateQueries({ queryKey: ['pages'] })
      navigate(`/spaces/pages/${p.id}`)
    },
  })

  const addSpace = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newSpace.trim()) return
    const res = await spacesApi.createSpace(newSpace.trim())
    queryClient.invalidateQueries({ queryKey: ['spaces'] })
    setNewSpace('')
    setAdding(false)
    navigate(`/spaces?space=${res.data.id}`)
  }

  const removeSpace = async (s: Space) => {
    if (!confirm(`'${s.name}' 공간을 삭제할까요? 안의 페이지는 삭제되지 않고 '공간 없음'으로 남습니다.`)) return
    await spacesApi.deleteSpace(s.id)
    queryClient.invalidateQueries({ queryKey: ['spaces'] })
    queryClient.invalidateQueries({ queryKey: ['pages'] })
    if (spaceId === s.id) navigate('/spaces')
  }

  const f = filter.trim().toLowerCase()
  const recent = pages.filter((p) => !f || (p.title || '제목 없음').toLowerCase().includes(f)).slice(0, f ? 20 : 5)

  const row = (active: boolean) =>
    `group w-full flex items-center gap-2.5 px-3 py-2 rounded-[var(--radius-md)] text-[14px] border-none cursor-pointer transition-colors text-left
     ${active ? 'bg-surface-active text-content-primary' : 'bg-transparent text-content-secondary hover:bg-surface-hover'}`

  const allActive = !spaceId && !view && !currentPageId

  return (
    <div className="flex h-screen bg-surface-primary overflow-hidden">
      <IconBar />
      <aside className="w-[260px] flex-shrink-0 border-r border-border bg-surface-secondary flex flex-col overflow-hidden">
        <div className="h-[52px] flex items-center justify-between px-4 flex-shrink-0">
          <h2 className="text-[16px] font-semibold text-content-primary">스페이스</h2>
          <div className="flex items-center gap-3 text-content-tertiary">
            <span title="알림 (준비 중)"><Bell size={16} className="opacity-50" /></span>
            <button
              onClick={() => { setSearching((s) => !s); setFilter('') }}
              title="최근 페이지 검색"
              aria-label="최근 페이지 검색"
              className="hover:text-content-primary border-none bg-transparent cursor-pointer text-inherit"
            >
              <Search size={16} />
            </button>
          </div>
        </div>
        {searching && (
          <div className="px-3 pb-2">
            <input
              autoFocus
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="검색"
              className="w-full px-3 py-1.5 bg-surface-primary border border-border rounded-[var(--radius-md)] text-[13px] text-content-primary focus:outline-none focus:border-accent-primary"
            />
          </div>
        )}

        <div className="px-2 space-y-0.5">
          <button className={row(false)} onClick={() => create.mutate()} disabled={create.isPending}>
            <FilePlus2 size={17} /> 새 페이지
          </button>
        </div>
        <div className="px-2 mt-3 space-y-0.5">
          <button className={row(allActive)} onClick={() => navigate('/spaces')}>
            <Library size={17} /> 전체
          </button>
        </div>

        <div className="flex-1 overflow-y-auto pb-3">
          <div className="px-5 pt-5 pb-1.5 text-xs text-content-tertiary">최근</div>
          <div className="px-2 space-y-0.5">
            {recent.length === 0 ? (
              <div className="px-3 py-2 text-[13px] text-content-muted">{pages.length ? '결과 없음' : '페이지가 없습니다'}</div>
            ) : (
              recent.map((p) => (
                <button key={p.id} className={row(p.id === currentPageId)} onClick={() => navigate(`/spaces/pages/${p.id}`)}>
                  <FileText size={16} className="flex-shrink-0" />
                  <span className="truncate">{p.title || '제목 없음'}</span>
                </button>
              ))
            )}
          </div>

          <div className="px-5 pt-5 pb-1.5 flex items-center justify-between text-xs text-content-tertiary">
            공간
            <button
              onClick={() => setAdding((a) => !a)}
              title="공간 만들기"
              aria-label="공간 만들기"
              className="hover:text-content-primary border-none bg-transparent cursor-pointer text-inherit"
            >
              {adding ? <X size={14} /> : <Plus size={14} />}
            </button>
          </div>
          <div className="px-2 space-y-0.5">
            {adding && (
              <form onSubmit={addSpace} className="px-1 pb-1">
                <input
                  autoFocus
                  value={newSpace}
                  onChange={(e) => setNewSpace(e.target.value)}
                  placeholder="공간 이름 (Enter)"
                  maxLength={100}
                  className="w-full px-3 py-1.5 bg-surface-primary border border-border rounded-[var(--radius-md)] text-[13px] text-content-primary focus:outline-none focus:border-accent-primary"
                />
              </form>
            )}
            {spaces.length === 0 && !adding && <div className="px-3 py-2 text-[13px] text-content-muted">공간이 없습니다</div>}
            {spaces.map((s) => (
              <div key={s.id} className={row(spaceId === s.id)} onClick={() => navigate(`/spaces?space=${s.id}`)} role="button">
                <Folder size={16} className="flex-shrink-0" />
                <span className="truncate flex-1">{s.name}</span>
                <span className="text-xs text-content-tertiary group-hover:hidden">{s.page_count || ''}</span>
                <button
                  onClick={(e) => { e.stopPropagation(); removeSpace(s) }}
                  title="공간 삭제"
                  aria-label={`${s.name} 삭제`}
                  className="hidden group-hover:block text-content-muted hover:text-accent-red border-none bg-transparent cursor-pointer"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="px-2 py-2 border-t border-border">
          <button className={row(view === 'trash')} onClick={() => navigate('/spaces?view=trash')}>
            <Trash2 size={17} /> 휴지통
          </button>
        </div>
      </aside>
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">{children}</main>
    </div>
  )
}

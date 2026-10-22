import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Check, Loader2, Star, Trash2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'
import axios from 'axios'
import SpacesLayout from '../components/spaces/SpacesLayout'
import { spacesApi } from '../api/spaces'
import type { PageDetail, Space } from '../types/space'

type Save = 'saved' | 'dirty' | 'saving' | 'error'

export default function PageEditorPage() {
  const { pageId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: page, error: loadError } = useQuery<PageDetail>({
    queryKey: ['page', pageId],
    queryFn: async () => (await spacesApi.getPage(pageId)).data,
    staleTime: Infinity, // 편집 중 서버 값으로 덮어쓰지 않는다
    refetchOnWindowFocus: false,
    retry: false,
  })
  const { data: spaces = [] } = useQuery<Space[]>({
    queryKey: ['spaces'],
    queryFn: async () => (await spacesApi.listSpaces()).data,
  })

  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [favorite, setFavorite] = useState(false)
  const [spaceId, setSpaceId] = useState<string | null>(null)
  const [mode, setMode] = useState<'edit' | 'preview'>('edit')
  const [save, setSave] = useState<Save>('saved')
  const loaded = useRef(false)
  const pending = useRef<{ title?: string; content?: string }>({})
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  useEffect(() => {
    loaded.current = false
    pending.current = {}
    setSave('saved')
  }, [pageId])

  useEffect(() => {
    if (page && !loaded.current) {
      loaded.current = true
      setTitle(page.title)
      setContent(page.content)
      setFavorite(page.is_favorite)
      setSpaceId(page.space_id)
    }
  }, [page])

  const flush = useCallback(async () => {
    clearTimeout(timer.current)
    const body = pending.current
    if (!Object.keys(body).length) return
    pending.current = {}
    setSave('saving')
    try {
      await spacesApi.updatePage(pageId, body)
      setSave(Object.keys(pending.current).length ? 'dirty' : 'saved')
      queryClient.invalidateQueries({ queryKey: ['pages'] })
    } catch (err) {
      pending.current = { ...body, ...pending.current }
      setSave('error')
      if (axios.isAxiosError(err) && err.response?.status === 409) alert('휴지통의 페이지는 수정할 수 없습니다')
    }
  }, [pageId, queryClient])

  const schedule = (patch: { title?: string; content?: string }) => {
    pending.current = { ...pending.current, ...patch }
    setSave('dirty')
    clearTimeout(timer.current)
    timer.current = setTimeout(flush, 800)
  }

  // 페이지를 떠나거나 닫을 때 남은 변경을 저장
  useEffect(() => {
    const onUnload = (e: BeforeUnloadEvent) => {
      if (Object.keys(pending.current).length) {
        flush()
        e.preventDefault()
      }
    }
    window.addEventListener('beforeunload', onUnload)
    return () => {
      window.removeEventListener('beforeunload', onUnload)
      if (Object.keys(pending.current).length) flush()
    }
  }, [flush])

  const toggleFav = async () => {
    const next = !favorite
    setFavorite(next)
    await spacesApi.updatePage(pageId, { is_favorite: next })
    queryClient.invalidateQueries({ queryKey: ['pages'] })
  }

  const moveTo = async (id: string) => {
    setSpaceId(id || null)
    await spacesApi.updatePage(pageId, id ? { space_id: id } : { clear_space: true })
    queryClient.invalidateQueries({ queryKey: ['pages'] })
    queryClient.invalidateQueries({ queryKey: ['spaces'] })
  }

  const trash = async () => {
    if (!confirm('이 페이지를 휴지통으로 옮길까요?')) return
    clearTimeout(timer.current)
    pending.current = {}
    await spacesApi.trashPage(pageId)
    queryClient.invalidateQueries({ queryKey: ['pages'] })
    queryClient.invalidateQueries({ queryKey: ['spaces'] })
    navigate(spaceId ? `/spaces?space=${spaceId}` : '/spaces')
  }

  const statusText = { saved: '저장됨', dirty: '변경됨', saving: '저장 중…', error: '저장 실패 — 다시 시도 중' }[save]
  const tab = (active: boolean) =>
    `px-3.5 py-1.5 rounded-full text-[13px] border-none cursor-pointer ${active ? 'bg-surface-active text-content-primary' : 'bg-transparent text-content-secondary hover:bg-surface-hover'}`

  if (loadError) {
    return (
      <SpacesLayout currentPageId={pageId}>
        <div className="p-10 text-content-secondary">
          페이지를 찾을 수 없습니다.{' '}
          <button onClick={() => navigate('/spaces')} className="text-accent-primary border-none bg-transparent cursor-pointer underline">목록으로</button>
        </div>
      </SpacesLayout>
    )
  }

  return (
    <SpacesLayout currentPageId={pageId}>
      <header className="h-[52px] border-b border-border flex items-center gap-3 px-5 flex-shrink-0">
        <button onClick={async () => { await flush(); navigate(spaceId ? `/spaces?space=${spaceId}` : '/spaces') }} title="목록으로" aria-label="목록으로" className="text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer">
          <ArrowLeft size={18} />
        </button>
        <span className={`flex items-center gap-1.5 text-xs ${save === 'error' ? 'text-accent-red' : 'text-content-tertiary'}`}>
          {save === 'saving' ? <Loader2 size={12} className="animate-spin" /> : save === 'saved' ? <Check size={12} /> : null}
          {statusText}
        </span>
        <div className="flex-1" />
        <select value={spaceId ?? ''} onChange={(e) => moveTo(e.target.value)} className="px-2.5 py-1.5 bg-surface-secondary border border-border rounded-[var(--radius-md)] text-[13px] text-content-primary max-w-[160px]" aria-label="공간 이동">
          <option value="">공간 없음</option>
          {spaces.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <div className="flex items-center gap-1">
          <button className={tab(mode === 'edit')} onClick={() => setMode('edit')}>편집</button>
          <button className={tab(mode === 'preview')} onClick={() => setMode('preview')}>미리보기</button>
        </div>
        <button onClick={toggleFav} title="즐겨찾기" aria-label="즐겨찾기" aria-pressed={favorite} className={`border-none bg-transparent cursor-pointer ${favorite ? 'text-accent-yellow' : 'text-content-tertiary hover:text-accent-yellow'}`}>
          <Star size={17} fill={favorite ? 'currentColor' : 'none'} />
        </button>
        <button onClick={trash} title="휴지통으로 이동" aria-label="휴지통으로 이동" className="text-content-tertiary hover:text-accent-red border-none bg-transparent cursor-pointer"><Trash2 size={17} /></button>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[860px] mx-auto px-8 py-8">
          <input
            value={title}
            onChange={(e) => { setTitle(e.target.value); schedule({ title: e.target.value }) }}
            placeholder="제목 없음"
            maxLength={200}
            className="w-full text-[32px] font-semibold bg-transparent border-none outline-none text-content-primary placeholder:text-content-muted mb-4"
          />
          {mode === 'edit' ? (
            <textarea
              value={content}
              onChange={(e) => { setContent(e.target.value); schedule({ content: e.target.value }) }}
              placeholder="마크다운으로 내용을 작성하세요…"
              className="w-full min-h-[60vh] resize-none bg-transparent border-none outline-none text-[15px] leading-7 text-content-primary placeholder:text-content-muted font-mono"
            />
          ) : (
            <div className="prose-sm text-[15px] leading-7 text-content-primary [&_h1]:text-2xl [&_h1]:font-semibold [&_h1]:mt-6 [&_h1]:mb-3 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:mt-5 [&_h2]:mb-2 [&_ul]:list-disc [&_ul]:pl-6 [&_ol]:list-decimal [&_ol]:pl-6 [&_table]:border-collapse [&_th]:border [&_th]:border-border [&_th]:px-3 [&_th]:py-1.5 [&_td]:border [&_td]:border-border [&_td]:px-3 [&_td]:py-1.5 [&_code]:bg-surface-tertiary [&_code]:px-1 [&_code]:rounded [&_pre]:bg-surface-tertiary [&_pre]:p-3 [&_pre]:rounded-[var(--radius-md)] [&_pre]:overflow-x-auto [&_a]:text-accent-primary">
              {content.trim() ? <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>{content}</ReactMarkdown> : <p className="text-content-muted">내용이 없습니다.</p>}
            </div>
          )}
        </div>
      </div>
    </SpacesLayout>
  )
}

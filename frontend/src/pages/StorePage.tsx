import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Flag, Loader2, Play, Search, Store, User as UserIcon } from 'lucide-react'
import IconBar from '../components/layout/IconBar'
import Sidebar from '../components/chat/Sidebar'
import AppPreviewPanel from '../components/chat/AppPreviewPanel'
import { storeApi, type QueueItem, type StoreApp } from '../api/apps'
import { chatApi } from '../api/chat'
import { useChatStore } from '../store/chatStore'
import { CATEGORY_LABEL, categoryLabel, errorDetail } from '../components/apps/appStoreMeta'
import type { Conversation } from '../types/chat'

function StoreCard({ app, onOpen }: { app: StoreApp; onOpen: () => void }) {
  return (
    <button onClick={onOpen} className="text-left rounded-xl border border-border bg-surface-secondary p-4 flex flex-col gap-2 hover:border-accent-primary transition-colors cursor-pointer">
      <div className="flex items-start gap-2">
        <div className="w-10 h-10 rounded-lg bg-accent-primary/15 text-accent-primary flex items-center justify-center flex-shrink-0 text-lg font-semibold">{app.title.slice(0, 1).toUpperCase()}</div>
        <div className="min-w-0 flex-1">
          <div className="text-[14px] font-medium text-content-primary truncate">{app.title}</div>
          <div className="text-[11px] text-content-tertiary flex items-center gap-1"><UserIcon size={10} /> {app.owner_name || '익명'} · v{app.version}</div>
        </div>
      </div>
      <p className="text-xs text-content-secondary line-clamp-3 min-h-[48px] break-words">{app.description || '설명이 없습니다.'}</p>
      <div className="flex items-center gap-1.5 flex-wrap text-[10px]">
        <span className="px-1.5 py-0.5 rounded bg-surface-tertiary text-content-secondary">{categoryLabel(app.category)}</span>
        {app.tags.slice(0, 3).map((t) => <span key={t} className="px-1.5 py-0.5 rounded bg-surface-tertiary text-content-tertiary">#{t}</span>)}
        <span className="ml-auto text-content-tertiary flex items-center gap-1"><Play size={9} /> {app.launch_count}</span>
      </div>
    </button>
  )
}

function ReportDialog({ app, onClose }: { app: StoreApp; onClose: () => void }) {
  const [reason, setReason] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const send = useMutation({
    mutationFn: () => storeApi.report(app.id, reason.trim()),
    onSuccess: () => setMsg('신고가 접수되었습니다. 감사합니다.'),
    onError: (e) => setMsg(errorDetail(e, '신고하지 못했습니다')),
  })
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="w-full max-w-md bg-surface-secondary border border-border rounded-xl p-5 space-y-3" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-[16px] font-semibold text-content-primary">'{app.title}' 신고</h3>
        <textarea autoFocus rows={4} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="신고 사유 (피싱, 악성 코드, 저작권 침해, 부적절한 내용 등)"
          className="w-full px-3 py-2 bg-surface-primary border border-border rounded-lg text-sm text-content-primary focus:outline-none focus:border-accent-primary resize-none" />
        {msg && <p className="text-xs text-content-secondary">{msg}</p>}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-2 rounded-lg text-sm text-content-muted hover:text-content-primary border-none bg-transparent cursor-pointer">닫기</button>
          <button onClick={() => send.mutate()} disabled={!reason.trim() || send.isPending || send.isSuccess} className="px-4 py-2 rounded-lg text-sm bg-accent-red text-white disabled:opacity-50 border-none cursor-pointer">
            {send.isPending ? <Loader2 size={14} className="animate-spin" /> : '신고'}
          </button>
        </div>
      </div>
    </div>
  )
}

const QUEUES: [string, string][] = [['pending', '승인 대기'], ['approved', '공개 중 (신고 많은 순)'], ['suspended', '정지됨'], ['rejected', '반려됨']]

function AdminQueue() {
  const qc = useQueryClient()
  const [status, setStatus] = useState('pending')
  const { data: items = [], isLoading } = useQuery({ queryKey: ['store-queue', status], queryFn: async () => (await storeApi.adminQueue(status)).data })
  const act = useMutation({
    mutationFn: ({ id, action }: { id: string; action: 'approve' | 'reject' | 'suspend' }) => {
      const note = action === 'approve' ? undefined : prompt(action === 'reject' ? '반려 사유 (소유자에게 표시됩니다)' : '정지 사유') ?? undefined
      return storeApi.moderate(id, action, note)
    },
    onSettled: () => { qc.invalidateQueries({ queryKey: ['store-queue'] }); qc.invalidateQueries({ queryKey: ['store-apps'] }) },
  })
  const Btn = ({ it, action, label, cls }: { it: QueueItem; action: 'approve' | 'reject' | 'suspend'; label: string; cls: string }) => (
    <button onClick={() => act.mutate({ id: it.id, action })} disabled={act.isPending} className={`px-2.5 py-1 rounded-md text-xs border-none cursor-pointer disabled:opacity-50 ${cls}`}>{label}</button>
  )
  return (
    <div className="mt-4">
      <div className="flex gap-1 flex-wrap mb-3">
        {QUEUES.map(([k, l]) => (
          <button key={k} onClick={() => setStatus(k)} className={`px-3 py-1.5 rounded-lg text-xs cursor-pointer border-none ${status === k ? 'bg-accent-primary text-white' : 'bg-surface-secondary text-content-muted hover:text-content-primary'}`}>{l}</button>
        ))}
      </div>
      {isLoading ? <Loader2 size={14} className="animate-spin" /> : items.length === 0 ? <p className="text-sm text-content-muted py-6">항목이 없습니다.</p> : (
        <div className="space-y-2">
          {items.map((it) => (
            <div key={it.id} className="rounded-xl border border-border bg-surface-secondary p-4">
              <div className="flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-content-primary">{it.title} <span className="text-xs text-content-tertiary">· {it.owner_name} · {it.kind === 'server' ? '서버형' : '정적'} v{it.version}</span></div>
                  <p className="text-xs text-content-secondary mt-1 break-words">{it.description || '(설명 없음)'}</p>
                  {it.moderation_note && <p className="text-xs text-accent-amber mt-1 break-words">메모: {it.moderation_note}</p>}
                  {it.reports > 0 && (
                    <div className="mt-2 text-xs text-accent-red">신고 {it.reports}건{it.reasons.map((r, i) => <div key={i} className="text-content-secondary break-words">- {r}</div>)}</div>
                  )}
                </div>
                <div className="flex flex-col gap-1 flex-shrink-0">
                  {status !== 'approved' && <Btn it={it} action="approve" label="승인" cls="bg-accent-done/20 text-accent-done" />}
                  {status === 'approved' && <Btn it={it} action="suspend" label="정지" cls="bg-accent-red/15 text-accent-red" />}
                  {status === 'pending' && <Btn it={it} action="reject" label="반려" cls="bg-surface-tertiary text-content-secondary" />}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/** App Store: 다른 사용자가 공개한 웹앱을 둘러보고 열어 본다 (로그인 없이 누구나 접속할 수 있는 앱). */
export default function StorePage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const openId = params.get('open')
  const { setConversations } = useChatStore()
  const [q, setQ] = useState('')
  const [category, setCategory] = useState('')
  const [sort, setSort] = useState<'popular' | 'new'>('popular')
  const [tab, setTab] = useState<'store' | 'admin'>('store')
  const [reporting, setReporting] = useState<StoreApp | null>(null)

  useEffect(() => {
    chatApi.getConversations().then((r) => setConversations(r.data as Conversation[]))
  }, [setConversations])

  const { data: info } = useQuery({ queryKey: ['store-info'], queryFn: async () => (await storeApi.info()).data, retry: false })
  const { data: apps = [], isLoading } = useQuery({
    queryKey: ['store-apps', q, category, sort],
    queryFn: async () => (await storeApi.list({ q: q || undefined, category: category || undefined, sort })).data,
  })
  const selected = apps.find((a) => a.id === openId) ?? null
  const { data: fetched } = useQuery({
    queryKey: ['store-app', openId],
    queryFn: async () => (await storeApi.get(openId as string)).data,
    enabled: !!openId && !selected,
    retry: false,
  })
  const current = selected ?? fetched ?? null

  return (
    <div className="flex h-screen bg-surface-primary overflow-hidden">
      <IconBar />
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {openId && current ? (
          <>
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border bg-surface-secondary">
              <button onClick={() => setParams({})} className="flex items-center gap-1 text-sm text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer"><ArrowLeft size={15} /> 스토어</button>
              <span className="text-sm font-medium text-content-primary truncate">{current.title}</span>
              <span className="text-xs text-content-tertiary truncate">by {current.owner_name || '익명'}</span>
              <div className="flex-1" />
              <button onClick={() => setReporting(current)} className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs border border-border text-content-secondary hover:text-accent-red cursor-pointer bg-transparent"><Flag size={12} /> 신고</button>
            </div>
            <div className="flex-1 min-h-0">
              <AppPreviewPanel key={current.id} name={current.title} launch={() => storeApi.launch(current.id)} />
            </div>
          </>
        ) : (
          <div className="flex-1 overflow-y-auto px-8 py-8">
            <div className="max-w-6xl">
              <div className="flex items-center gap-3">
                <h1 className="text-[26px] font-semibold text-content-primary flex items-center gap-2"><Store size={24} /> App Store</h1>
                {info?.is_admin && (
                  <div className="flex gap-1 ml-4">
                    {([['store', '둘러보기'], ['admin', '검수']] as const).map(([k, l]) => (
                      <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs cursor-pointer border-none ${tab === k ? 'bg-accent-primary text-white' : 'bg-surface-secondary text-content-muted hover:text-content-primary'}`}>{l}</button>
                    ))}
                  </div>
                )}
              </div>
              <p className="mt-1 text-[14px] text-content-secondary">사용자가 공개한 웹앱입니다. 로그인 없이 누구나 열 수 있는 앱이며, 신뢰할 수 없는 앱에는 개인정보를 입력하지 마세요.</p>

              {tab === 'admin' && info?.is_admin ? <AdminQueue /> : (
                <>
                  <div className="mt-5 flex flex-wrap items-center gap-2">
                    <div className="relative flex-1 min-w-[220px] max-w-md">
                      <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-content-muted" />
                      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="앱 검색"
                        className="w-full pl-9 pr-3 py-2 bg-surface-secondary border border-border rounded-lg text-sm text-content-primary focus:outline-none focus:border-accent-primary" />
                    </div>
                    {(['popular', 'new'] as const).map((s) => (
                      <button key={s} onClick={() => setSort(s)} className={`px-3 py-1.5 rounded-lg text-xs cursor-pointer border-none ${sort === s ? 'bg-accent-primary text-white' : 'bg-surface-secondary text-content-muted hover:text-content-primary'}`}>{s === 'popular' ? '인기순' : '최신순'}</button>
                    ))}
                  </div>
                  <div className="mt-3 flex gap-1.5 flex-wrap">
                    {[['', '전체'], ...Object.entries(CATEGORY_LABEL)].map(([k, l]) => (
                      <button key={k} onClick={() => setCategory(k)} className={`px-3 py-1 rounded-full text-xs cursor-pointer border ${category === k ? 'border-accent-primary text-accent-primary bg-accent-primary/10' : 'border-border text-content-muted hover:text-content-primary bg-transparent'}`}>{l}</button>
                    ))}
                  </div>
                  {isLoading ? (
                    <div className="mt-8 text-sm text-content-muted"><Loader2 size={14} className="animate-spin inline mr-1" /> 불러오는 중...</div>
                  ) : apps.length === 0 ? (
                    <div className="mt-8 rounded-xl border border-dashed border-border p-10 text-center text-sm text-content-muted">
                      <Store size={28} className="mx-auto mb-2 opacity-50" />
                      <p>{q || category ? '조건에 맞는 앱이 없습니다.' : '아직 공개된 앱이 없습니다.'}</p>
                      <p className="text-xs mt-1 text-content-tertiary">My Apps 에서 내 앱을 'App Store에 등록'하면 여기에 나타납니다.</p>
                      <button onClick={() => navigate('/apps')} className="mt-4 px-3 py-1.5 rounded-lg border border-border text-content-secondary hover:text-content-primary text-sm cursor-pointer bg-transparent">My Apps 로 이동</button>
                    </div>
                  ) : (
                    <div className="mt-5 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                      {apps.map((a) => <StoreCard key={a.id} app={a} onOpen={() => setParams({ open: a.id })} />)}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}
      </main>
      {reporting && <ReportDialog app={reporting} onClose={() => setReporting(null)} />}
    </div>
  )
}

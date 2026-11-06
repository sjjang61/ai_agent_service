import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Check, ClipboardCheck, Eye, Loader2, Pause, X } from 'lucide-react'
import IconBar from '../components/layout/IconBar'
import Sidebar from '../components/chat/Sidebar'
import AppPreviewPanel from '../components/chat/AppPreviewPanel'
import { storeApi, type QueueItem } from '../api/apps'
import { chatApi } from '../api/chat'
import { useChatStore } from '../store/chatStore'
import { categoryLabel, errorDetail } from '../components/apps/appStoreMeta'
import type { Conversation } from '../types/chat'

const QUEUES: [string, string][] = [['pending', '승인 대기'], ['suspended', '정지됨 (신고)'], ['approved', '공개 중'], ['rejected', '반려됨']]
type Action = 'approve' | 'reject' | 'suspend'
const ACTION_LABEL: Record<Action, string> = { approve: '승인', reject: '반려', suspend: '정지' }

/** 승인·반려·정지 확인 창. 반려·정지는 사유(소유자에게 표시됨)를 받는다. */
function ActionDialog({ item, action, onClose, onDone }: { item: QueueItem; action: Action; onClose: () => void; onDone: () => void }) {
  const [note, setNote] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const run = useMutation({
    mutationFn: () => storeApi.moderate(item.id, action, note.trim() || undefined),
    onSuccess: () => { onDone(); onClose() },
    onError: (e) => setErr(errorDetail(e, '처리하지 못했습니다')),
  })
  const needNote = action !== 'approve'
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="w-full max-w-md bg-surface-secondary border border-border rounded-xl p-5 space-y-3" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-[16px] font-semibold text-content-primary">'{item.title}' {ACTION_LABEL[action]}</h3>
        <p className="text-xs text-content-secondary">
          {action === 'approve' ? '승인하면 로그인 없이 누구나 이 앱에 접속할 수 있고 스토어 목록에 노출됩니다.' : action === 'reject' ? '반려하면 앱이 비공개로 돌아가고 소유자에게 사유가 표시됩니다.' : '정지하면 서비스가 즉시 중단되고 컨테이너가 내려갑니다. 소유자에게 사유가 표시됩니다.'}
        </p>
        {needNote ? (
          <textarea autoFocus rows={3} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} placeholder={`${ACTION_LABEL[action]} 사유`}
            className="w-full px-3 py-2 bg-surface-primary border border-border rounded-lg text-sm text-content-primary focus:outline-none focus:border-accent-primary resize-none" />
        ) : (
          <textarea rows={2} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} placeholder="메모 (선택)"
            className="w-full px-3 py-2 bg-surface-primary border border-border rounded-lg text-sm text-content-primary focus:outline-none focus:border-accent-primary resize-none" />
        )}
        {err && <p className="text-xs text-accent-red">{err}</p>}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-2 rounded-lg text-sm text-content-muted hover:text-content-primary border-none bg-transparent cursor-pointer">취소</button>
          <button onClick={() => run.mutate()} disabled={run.isPending || (needNote && !note.trim())}
            className={`px-4 py-2 rounded-lg text-sm text-white disabled:opacity-50 border-none cursor-pointer ${action === 'approve' ? 'bg-accent-done' : action === 'reject' ? 'bg-content-muted' : 'bg-accent-red'}`}>
            {run.isPending ? <Loader2 size={14} className="animate-spin" /> : ACTION_LABEL[action]}
          </button>
        </div>
      </div>
    </div>
  )
}

function ActionButtons({ item, status, onAct }: { item: QueueItem; status: string; onAct: (a: Action) => void }) {
  const base = 'flex items-center gap-1 px-2.5 py-1 rounded-md text-xs border-none cursor-pointer'
  return (
    <div className="flex gap-1.5 flex-wrap" data-id={item.id}>
      {status !== 'approved' && <button onClick={() => onAct('approve')} className={`${base} bg-accent-done/20 text-accent-done`}><Check size={12} /> 승인</button>}
      {(status === 'pending' || status === 'suspended') && <button onClick={() => onAct('reject')} className={`${base} bg-surface-tertiary text-content-secondary`}><X size={12} /> 반려</button>}
      {status === 'approved' && <button onClick={() => onAct('suspend')} className={`${base} bg-accent-red/15 text-accent-red`}><Pause size={12} /> 정지</button>}
    </div>
  )
}

/** 앱 승인: 공개를 요청한 앱(승인 대기), 신고로 정지된 앱을 검토해 승인·반려·정지한다. 미리보기로 앱을 직접 열어 볼 수 있다. */
export default function ReviewPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [params, setParams] = useSearchParams()
  const status = params.get('status') ?? 'pending'
  const previewId = params.get('preview')
  const { setConversations } = useChatStore()
  const [acting, setActing] = useState<{ item: QueueItem; action: Action } | null>(null)

  useEffect(() => {
    chatApi.getConversations().then((r) => setConversations(r.data as Conversation[]))
  }, [setConversations])

  const { data: info, isLoading: infoLoading } = useQuery({ queryKey: ['store-info'], queryFn: async () => (await storeApi.info()).data, retry: false })
  const { data: items = [], isLoading } = useQuery({
    queryKey: ['store-queue', status],
    queryFn: async () => (await storeApi.adminQueue(status)).data,
    enabled: !!info?.is_admin,
  })
  const preview = items.find((i) => i.id === previewId) ?? null
  const done = () => {
    qc.invalidateQueries({ queryKey: ['store-queue'] })
    qc.invalidateQueries({ queryKey: ['store-apps'] })
    qc.invalidateQueries({ queryKey: ['store-info'] })
    setParams({ status })
  }

  return (
    <div className="flex h-screen bg-surface-primary overflow-hidden">
      <IconBar />
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {infoLoading ? (
          <div className="p-8 text-sm text-content-muted"><Loader2 size={14} className="animate-spin inline mr-1" /> 불러오는 중...</div>
        ) : !info?.is_admin ? (
          <div className="p-8 text-sm text-content-muted">검수 권한이 없습니다.</div>
        ) : preview ? (
          <>
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border bg-surface-secondary flex-wrap">
              <button onClick={() => setParams({ status })} className="flex items-center gap-1 text-sm text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer"><ArrowLeft size={15} /> 목록</button>
              <span className="text-sm font-medium text-content-primary truncate">{preview.title}</span>
              <span className="text-xs text-content-tertiary">{preview.owner_name} · {preview.kind === 'server' ? '서버형' : '정적'} v{preview.version}</span>
              <div className="flex-1" />
              <ActionButtons item={preview} status={status} onAct={(a) => setActing({ item: preview, action: a })} />
            </div>
            <div className="flex-1 min-h-0">
              <AppPreviewPanel key={preview.id} name={preview.title} launch={() => storeApi.reviewLaunch(preview.id)} />
            </div>
          </>
        ) : (
          <div className="flex-1 overflow-y-auto px-8 py-8">
            <div className="max-w-5xl">
              <button onClick={() => navigate('/store')} className="flex items-center gap-1 text-xs text-content-muted hover:text-content-primary border-none bg-transparent cursor-pointer mb-2"><ArrowLeft size={13} /> App Store</button>
              <h1 className="text-[26px] font-semibold text-content-primary flex items-center gap-2"><ClipboardCheck size={24} /> 앱 승인</h1>
              <p className="mt-1 text-[14px] text-content-secondary">공개를 요청한 앱을 검토합니다. 미리보기로 앱을 직접 열어 보고 승인·반려하세요. 현재는 사용자 역할이 없어 로그인한 모든 사용자가 검수할 수 있습니다.</p>

              <div className="mt-5 flex gap-1 flex-wrap">
                {QUEUES.map(([k, l]) => (
                  <button key={k} onClick={() => setParams({ status: k })} className={`px-3 py-1.5 rounded-lg text-xs cursor-pointer border-none ${status === k ? 'bg-accent-primary text-white' : 'bg-surface-secondary text-content-muted hover:text-content-primary'}`}>
                    {l}{k === 'pending' && (info?.review_pending ?? 0) > 0 && status !== 'pending' ? ` (${info.review_pending})` : ''}
                  </button>
                ))}
              </div>

              {isLoading ? (
                <div className="mt-6 text-sm text-content-muted"><Loader2 size={14} className="animate-spin inline mr-1" /> 불러오는 중...</div>
              ) : items.length === 0 ? (
                <div className="mt-6 rounded-xl border border-dashed border-border p-10 text-center text-sm text-content-muted">
                  <ClipboardCheck size={28} className="mx-auto mb-2 opacity-50" />
                  {status === 'pending' ? '승인을 기다리는 앱이 없습니다.' : '항목이 없습니다.'}
                </div>
              ) : (
                <div className="mt-5 space-y-3">
                  {items.map((it) => (
                    <div key={it.id} className="rounded-xl border border-border bg-surface-secondary p-4">
                      <div className="flex items-start gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-[15px] font-medium text-content-primary">{it.title}</span>
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-tertiary text-content-secondary">{it.kind === 'server' ? '서버형' : '정적'}</span>
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-tertiary text-content-secondary">{categoryLabel(it.category)}</span>
                            <span className="text-[11px] text-content-tertiary">v{it.version} · {it.owner_name || '익명'}</span>
                          </div>
                          <p className="text-xs text-content-secondary mt-1.5 break-words whitespace-pre-wrap">{it.description || '(설명 없음)'}</p>
                          {it.tags.length > 0 && <p className="text-[11px] text-content-tertiary mt-1">{it.tags.map((t) => `#${t}`).join(' ')}</p>}
                          {it.moderation_note && <p className="text-xs text-accent-amber mt-1.5 break-words">메모: {it.moderation_note}</p>}
                          {it.reports > 0 && (
                            <div className="mt-2 text-xs text-accent-red">신고 {it.reports}건{it.reasons.map((r, i) => <div key={i} className="text-content-secondary break-words">- {r}</div>)}</div>
                          )}
                        </div>
                        <div className="flex flex-col gap-2 items-end flex-shrink-0">
                          <button onClick={() => setParams({ status, preview: it.id })} className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs border border-border text-content-secondary hover:text-content-primary cursor-pointer bg-transparent"><Eye size={12} /> 미리보기</button>
                          <ActionButtons item={it} status={status} onAct={(a) => setActing({ item: it, action: a })} />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </main>
      {acting && <ActionDialog item={acting.item} action={acting.action} onClose={() => setActing(null)} onDone={done} />}
    </div>
  )
}

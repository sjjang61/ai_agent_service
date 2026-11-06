import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ExternalLink, Globe, Loader2, Lock, Pencil, Play, Rocket, Square, Store } from 'lucide-react'
import IconBar from '../components/layout/IconBar'
import Sidebar from '../components/chat/Sidebar'
import AppPreviewPanel from '../components/chat/AppPreviewPanel'
import { appsApi, type DeployedApp } from '../api/apps'
import PublishDialog from '../components/apps/PublishDialog'
import { errorDetail } from '../components/apps/appStoreMeta'
import { chatApi } from '../api/chat'
import { useChatStore } from '../store/chatStore'
import type { Conversation } from '../types/chat'

const STATUS: Record<DeployedApp['status'], { label: string; dot: string }> = {
  running: { label: '실행 중', dot: 'bg-accent-done' },
  starting: { label: '시작 중', dot: 'bg-accent-primary animate-pulse' },
  stopped: { label: '중지됨', dot: 'bg-content-muted' },
  failed: { label: '실패', dot: 'bg-accent-red' },
}

const errText = (e: unknown) => errorDetail(e, '앱을 시작하지 못했습니다')

function VisibilityBadge({ app }: { app: DeployedApp }) {
  if (app.visibility !== 'public') return <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-surface-tertiary text-content-tertiary"><Lock size={9} /> 비공개</span>
  const m = { approved: ['공개 중', 'bg-accent-done/15 text-accent-done'], pending: ['승인 대기', 'bg-accent-amber/15 text-accent-amber'], suspended: ['정지됨', 'bg-accent-red/15 text-accent-red'], rejected: ['반려됨', 'bg-accent-red/15 text-accent-red'], '': ['공개', ''] }[app.moderation_status] ?? ['공개', '']
  return <span className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded ${m[1]}`}><Globe size={9} /> {m[0]}</span>
}

function AppCard({ app, running, onRun, onPublish, onUnpublish }: { app: DeployedApp; running: boolean; onRun: () => void; onPublish: () => void; onUnpublish: () => void }) {
  const openNew = async () => {
    const w = window.open('', '_blank')
    try {
      const u = await appsApi.launch(app.id)
      if (w) w.location.href = u
    } catch {
      w?.close()
    }
  }
  const st = STATUS[app.status]
  const when = app.last_request_at ? new Date(app.last_request_at + (app.last_request_at.endsWith('Z') ? '' : 'Z')).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : null
  return (
    <div className="rounded-xl border border-border bg-surface-secondary p-4 flex flex-col gap-3">
      <div className="flex items-start gap-2">
        <div className="w-9 h-9 rounded-lg bg-accent-primary/15 text-accent-primary flex items-center justify-center flex-shrink-0"><Rocket size={17} /></div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="text-[14px] font-medium text-content-primary truncate">{app.name}</span>
            <VisibilityBadge app={app} />
          </div>
          <div className="text-[11px] text-content-tertiary">{app.kind === 'server' ? '서버형' : '정적'} · v{app.version}{app.port ? ` · :${app.port}` : ''}</div>
        </div>
      </div>
      <div className="flex items-center gap-1.5 text-xs text-content-secondary">
        <span className={`w-2 h-2 rounded-full ${st.dot}`} />
        {st.label}
        {when && <span className="text-content-tertiary">· 마지막 접속 {when}</span>}
      </div>
      {app.moderation_note && app.visibility !== 'private' || app.moderation_status === 'rejected' ? <p className="text-xs text-accent-amber whitespace-pre-wrap break-words">{app.moderation_note}</p> : null}
      {app.status === 'failed' && app.error && <p className="text-xs text-accent-red whitespace-pre-wrap break-words max-h-20 overflow-auto">{app.error}</p>}
      <div className="flex items-center gap-2 mt-auto">
        <button onClick={onRun} disabled={running} className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-accent-primary text-white text-sm font-medium hover:opacity-90 disabled:opacity-60 cursor-pointer border-none">
          {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          {running ? '시작 중...' : '실행'}
        </button>
        <button onClick={openNew} title="새 창에서 열기" aria-label="새 창에서 열기" className="p-2 rounded-lg border border-border text-content-secondary hover:text-content-primary bg-transparent cursor-pointer"><ExternalLink size={14} /></button>
      </div>
      <div className="flex items-center gap-2 text-xs">
        {app.visibility === 'public' ? (
          <>
            <button onClick={onPublish} className="flex items-center gap-1 text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer"><Pencil size={11} /> 스토어 정보 수정</button>
            <span className="flex-1" />
            <button onClick={onUnpublish} className="text-accent-red hover:underline border-none bg-transparent cursor-pointer">등록 취소</button>
          </>
        ) : (
          <button onClick={onPublish} className="flex items-center gap-1 text-accent-primary hover:underline border-none bg-transparent cursor-pointer"><Store size={11} /> App Store에 등록 (공개)</button>
        )}
      </div>
    </div>
  )
}

/** My Apps: 내가 배포한 웹앱 목록. '실행'을 누르면 (꺼져 있으면 시작한 뒤) 이 화면 안에서 앱을 열어 보여 준다. */
export default function MyAppsPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [params, setParams] = useSearchParams()
  const openId = params.get('open')
  const [error, setError] = useState<string | null>(null)
  const [runningId, setRunningId] = useState<string | null>(null)
  const [publishing, setPublishing] = useState<DeployedApp | null>(null)
  const unpublish = useMutation({
    mutationFn: async (a: DeployedApp) => appsApi.unpublish(a.id),
    onSettled: () => qc.invalidateQueries({ queryKey: ['deployed-apps'] }),
  })
  const { setConversations } = useChatStore()

  // 왼쪽 사이드바(대화 목록)를 채운다
  useEffect(() => {
    chatApi.getConversations().then((r) => setConversations(r.data as Conversation[]))
  }, [setConversations])

  const { data: apps = [], isLoading } = useQuery({
    queryKey: ['deployed-apps'],
    queryFn: async () => (await appsApi.list()).data,
    refetchInterval: (q) => ((q.state.data as DeployedApp[] | undefined)?.some((a) => a.status === 'starting') ? 2000 : 10000),
  })
  const selected = apps.find((a) => a.id === openId) ?? null

  const run = useMutation({
    mutationFn: async (app: DeployedApp) => {
      setError(null)
      setRunningId(app.id)
      return app.status === 'running' ? app : (await appsApi.start(app.id)).data
    },
    onSuccess: (app) => {
      if (app.status === 'running') setParams({ open: app.id })
      else setError(`${app.name}: ${app.error ?? '앱을 시작하지 못했습니다'}`)
    },
    onError: (e) => setError(errText(e)),
    onSettled: () => {
      setRunningId(null)
      qc.invalidateQueries({ queryKey: ['deployed-apps'] })
    },
  })
  const stop = useMutation({
    mutationFn: async (id: string) => appsApi.stop(id),
    onSettled: () => qc.invalidateQueries({ queryKey: ['deployed-apps'] }),
  })

  // 사이드바 등에서 ?open=ID 로 들어왔는데 꺼져 있으면 자동으로 시작한다
  const autoStarted = useRef<string | null>(null)
  useEffect(() => {
    if (selected && selected.status !== 'running' && selected.status !== 'starting' && autoStarted.current !== selected.id) {
      autoStarted.current = selected.id
      run.mutate(selected)
    }
    if (!selected) autoStarted.current = null
  }, [selected?.id, selected?.status]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex h-screen bg-surface-primary overflow-hidden">
      <IconBar />
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {selected ? (
          <>
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border bg-surface-secondary">
              <button onClick={() => setParams({})} className="flex items-center gap-1 text-sm text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer">
                <ArrowLeft size={15} /> 목록
              </button>
              <span className="text-sm font-medium text-content-primary truncate">{selected.name}</span>
              <span className={`w-2 h-2 rounded-full ${STATUS[selected.status].dot}`} title={STATUS[selected.status].label} />
              <div className="flex-1" />
              {selected.status === 'running' && (
                <button onClick={() => stop.mutate(selected.id)} disabled={stop.isPending} className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs border border-border text-content-secondary hover:text-content-primary cursor-pointer bg-transparent disabled:opacity-50">
                  <Square size={12} /> 중지
                </button>
              )}
            </div>
            <div className="flex-1 min-h-0">
              {selected.status === 'running' ? (
                <AppPreviewPanel key={selected.id} name={selected.name} launch={() => appsApi.launch(selected.id)} />
              ) : (
                <div className="h-full flex flex-col items-center justify-center gap-3 text-sm text-content-muted px-6 text-center">
                  {selected.status === 'failed' ? (
                    <>
                      <p className="text-accent-red whitespace-pre-wrap break-words max-w-xl">{error ?? selected.error ?? '앱을 시작하지 못했습니다'}</p>
                      <button onClick={() => run.mutate(selected)} className="px-3 py-1.5 rounded-lg bg-accent-primary text-white text-sm cursor-pointer border-none">다시 시도</button>
                    </>
                  ) : (
                    <><Loader2 size={20} className="animate-spin" /> 앱을 시작하는 중입니다...</>
                  )}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 overflow-y-auto px-8 py-8">
            <div className="max-w-5xl">
              <h1 className="text-[26px] font-semibold text-content-primary">My Apps</h1>
              <p className="mt-1 text-[14px] text-content-secondary">채팅에서 에이전트가 배포한 웹앱입니다. 쓰지 않으면 자동으로 내려가고, 실행하면 다시 시작합니다.</p>
              {error && <p className="mt-3 text-sm text-accent-red whitespace-pre-wrap break-words">{error}</p>}
              {isLoading ? (
                <div className="mt-8 text-sm text-content-muted"><Loader2 size={14} className="animate-spin inline mr-1" /> 불러오는 중...</div>
              ) : apps.length === 0 ? (
                <div className="mt-8 rounded-xl border border-dashed border-border p-10 text-center text-sm text-content-muted">
                  <Rocket size={28} className="mx-auto mb-2 opacity-50" />
                  <p>배포한 앱이 없습니다.</p>
                  <p className="text-xs mt-1 text-content-tertiary">채팅에서 에이전트에게 웹앱을 만들고 "배포해 줘"라고 요청해 보세요.</p>
                  <button onClick={() => navigate('/')} className="mt-4 px-3 py-1.5 rounded-lg border border-border text-content-secondary hover:text-content-primary text-sm cursor-pointer bg-transparent">채팅으로 이동</button>
                </div>
              ) : (
                <div className="mt-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {apps.map((a) => (
                    <AppCard key={a.id} app={a} running={runningId === a.id || a.status === 'starting'} onRun={() => run.mutate(a)} onPublish={() => setPublishing(a)}
                      onUnpublish={() => confirm(`'${a.name}' 의 등록을 취소할까요?\n공개 주소로의 접속이 즉시 차단되고 스토어 목록에서 사라집니다.`) && unpublish.mutate(a)} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </main>
      {publishing && <PublishDialog app={publishing} onClose={() => setPublishing(null)} onDone={() => qc.invalidateQueries({ queryKey: ['deployed-apps'] })} />}
    </div>
  )
}

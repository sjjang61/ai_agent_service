import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ExternalLink, Loader2, Play, Square, Trash2, ScrollText, Copy, Lock, Rocket } from 'lucide-react'
import { appsApi, type DeployedApp } from '../../api/apps'
import { T } from '../skills/typography'

const STATUS: Record<DeployedApp['status'], { label: string; cls: string }> = {
  running: { label: '실행 중', cls: 'bg-accent-done/15 text-accent-done' },
  starting: { label: '시작 중', cls: 'bg-accent-primary/15 text-accent-primary' },
  stopped: { label: '대기 (요청 시 자동 시작)', cls: 'bg-surface-tertiary text-content-muted' },
  failed: { label: '실패', cls: 'bg-accent-red/15 text-accent-red' },
}

function AppRow({ app }: { app: DeployedApp }) {
  const qc = useQueryClient()
  const [showLogs, setShowLogs] = useState(false)
  const [logs, setLogs] = useState<string | null>(null)
  const refresh = () => qc.invalidateQueries({ queryKey: ['deployed-apps'] })
  const start = useMutation({ mutationFn: () => appsApi.start(app.id), onSettled: refresh })
  const stop = useMutation({ mutationFn: () => appsApi.stop(app.id), onSettled: refresh })
  const remove = useMutation({ mutationFn: () => appsApi.remove(app.id), onSettled: refresh })
  const loadLogs = async () => {
    setShowLogs((v) => !v)
    if (!showLogs) setLogs((await appsApi.logs(app.id)).data.logs || '(로그 없음)')
  }
  const st = STATUS[app.status]
  const busy = start.isPending || stop.isPending || remove.isPending
  const copy = () => app.url && navigator.clipboard?.writeText(app.url)

  return (
    <div className="rounded-xl border border-border bg-surface-secondary p-4">
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[14px] font-medium text-content-primary">{app.name}</span>
            <span className={`text-[11px] px-2 py-0.5 rounded-full ${st.cls}`}>{app.status === 'starting' || start.isPending ? '시작 중' : st.label}</span>
            <span className="text-[11px] text-content-tertiary">{app.kind === 'server' ? '서버형' : '정적'} · v{app.version} · :{app.port}</span>
            {app.require_token && <span title="접근 토큰이 필요한 비공개 앱" className="text-content-tertiary"><Lock size={12} /></span>}
          </div>
          {app.url && (
            <a href={app.url} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-xs text-accent-primary hover:underline break-all">
              {app.url.replace(/\?t=.*/, app.require_token ? '?t=…' : '')} <ExternalLink size={11} />
            </a>
          )}
          {app.status === 'failed' && app.error && <p className="mt-1 text-xs text-accent-red whitespace-pre-wrap break-words max-h-24 overflow-auto">{app.error}</p>}
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <button onClick={copy} title="URL 복사" className="p-1.5 text-content-muted hover:text-content-primary"><Copy size={14} /></button>
          <button onClick={loadLogs} title="로그" className="p-1.5 text-content-muted hover:text-content-primary"><ScrollText size={14} /></button>
          {app.status === 'running' ? (
            <button onClick={() => stop.mutate()} disabled={busy} title="중지 (다음 요청에 다시 시작)" className="p-1.5 text-content-muted hover:text-content-primary disabled:opacity-50">
              {stop.isPending ? <Loader2 size={14} className="animate-spin" /> : <Square size={14} />}
            </button>
          ) : (
            <button onClick={() => start.mutate()} disabled={busy || app.status === 'starting'} title="시작" className="p-1.5 text-content-muted hover:text-content-primary disabled:opacity-50">
              {start.isPending ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            </button>
          )}
          <button onClick={() => confirm(`'${app.name}' 앱을 삭제하시겠습니까?\n배포 아카이브와 앱 데이터가 함께 삭제됩니다.`) && remove.mutate()} disabled={busy} title="삭제" className="p-1.5 text-content-muted hover:text-accent-red disabled:opacity-50"><Trash2 size={14} /></button>
        </div>
      </div>
      {showLogs && <pre className="mt-3 p-3 rounded-lg bg-surface-primary border border-border text-[11px] text-content-secondary whitespace-pre-wrap break-all max-h-60 overflow-auto">{logs ?? '불러오는 중...'}</pre>}
    </div>
  )
}

/** 에이전트가 deploy_web_app 으로 배포한 웹앱 목록. 컨테이너는 유휴 시 내려가고 다음 요청에 자동으로 다시 시작한다. */
export default function DeployedApps() {
  const { data: apps = [], isLoading } = useQuery({
    queryKey: ['deployed-apps'],
    queryFn: async () => (await appsApi.list()).data,
    refetchInterval: (q) => ((q.state.data as DeployedApp[] | undefined)?.some((a) => a.status === 'starting') ? 2000 : 10000),
  })
  return (
    <section className="space-y-3">
      <h2 className={`${T.section} pt-2 flex items-center gap-2`}><Rocket size={15} /> 배포된 앱</h2>
      {isLoading ? (
        <div className="text-sm text-content-muted"><Loader2 size={13} className="animate-spin inline mr-1" /> 불러오는 중...</div>
      ) : apps.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-content-muted">
          배포된 앱이 없습니다. 채팅에서 에이전트에게 웹앱을 만들고 "배포해 줘"라고 요청해 보세요.
          <p className="text-xs mt-1 text-content-tertiary">앱은 20000번대 포트로 열리며, 쓰지 않으면 컨테이너가 내려가고 접속하면 자동으로 다시 시작합니다.</p>
        </div>
      ) : (
        apps.map((a) => <AppRow key={a.id} app={a} />)
      )}
    </section>
  )
}

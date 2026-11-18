import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Plus, RefreshCw, Workflow } from 'lucide-react'
import IconBar from '../components/layout/IconBar'
import Sidebar from '../components/chat/Sidebar'
import { ACTIVE, STATUS_LABEL, formatDuration, functionsApi, type RunStatus } from '../api/functions'
import { driveError } from '../api/drive'
import CreateFunctionDialog from '../components/functions/CreateFunctionDialog'
import RunDetailDialog from '../components/functions/RunDetailDialog'
import StatusBadge from '../components/functions/StatusBadge'
import { TriggerRow } from '../components/functions/TriggersSection'
import { formatDateTimeMinute } from '../utils/time'

type Tab = 'functions' | 'runs' | 'triggers'

/** Workflow: 함수(Lambda 형 실행) 등록·관리와 실행 이력. 함수 하나를 실행하고 끝나는 단건 실행을 관리한다 (함수 연결은 아직 지원하지 않는다). */
export default function WorkflowPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [params, setParams] = useSearchParams()
  const tab: Tab = params.get('tab') === 'runs' ? 'runs' : params.get('tab') === 'triggers' ? 'triggers' : 'functions'
  const [creating, setCreating] = useState(false)
  const [openRun, setOpenRun] = useState<string | null>(null)
  const [fnFilter, setFnFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const { data: info, isLoading: infoLoading } = useQuery({ queryKey: ['functions-info'], queryFn: functionsApi.info, retry: false, staleTime: 60_000 })
  const usable = !!info?.enabled && !!info?.allowed
  const fns = useQuery({ queryKey: ['fn-list'], queryFn: functionsApi.list, enabled: usable, retry: false, refetchInterval: (q) => (q.state.data?.some((f) => f.last_run?.status && ACTIVE.includes(f.last_run.status)) ? 3000 : false) })
  const runs = useQuery({
    queryKey: ['fn-runs', fnFilter, statusFilter],
    queryFn: () => functionsApi.runs({ function_id: fnFilter || undefined, status: statusFilter || undefined, limit: 100 }),
    enabled: usable && tab === 'runs', retry: false,
    refetchInterval: (q) => (q.state.data?.some((r) => ACTIVE.includes(r.status)) ? 2500 : false),
  })
  const triggers = useQuery({ queryKey: ['fn-all-triggers'], queryFn: functionsApi.allTriggers, enabled: usable && tab === 'triggers', retry: false })
  const names = useMemo(() => Object.fromEntries((fns.data ?? []).map((f) => [f.id, f.name])), [fns.data])
  const refresh = () => { qc.invalidateQueries({ queryKey: ['fn-list'] }); qc.invalidateQueries({ queryKey: ['fn-runs'] }) }

  const setTab = (t: Tab) => setParams(t === 'functions' ? {} : { tab: t })
  const tabBtn = (t: Tab, label: string) => (
    <button role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
      className={`px-3 py-1.5 text-sm border-none bg-transparent cursor-pointer border-b-2 ${tab === t ? 'text-content-primary font-semibold border-b-accent-primary' : 'text-content-secondary border-b-transparent hover:text-content-primary'}`} style={{ borderBottomStyle: 'solid', borderBottomWidth: 2 }}>
      {label}
    </button>
  )
  const th = 'px-4 py-2.5 text-left text-xs font-medium text-content-secondary'
  const select = 'px-2.5 py-1.5 rounded-lg border border-border bg-surface-secondary text-xs text-content-primary'

  return (
    <div className="flex h-screen bg-surface-primary overflow-hidden">
      <IconBar />
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-auto">
        <div className="max-w-[960px] mx-auto px-6 pt-10 pb-24">
          <div className="flex items-center gap-2">
            <Workflow size={20} className="text-content-secondary" aria-hidden />
            <h1 className="flex-1 m-0 text-xl font-semibold text-content-primary">Workflow</h1>
            {usable && <>
              <button onClick={() => setCreating(true)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border-none bg-accent-primary text-white cursor-pointer"><Plus size={15} /> 새 함수</button>
              <button onClick={refresh} title="새로고침" aria-label="새로고침" className="p-2 rounded-lg border-none bg-transparent text-content-secondary hover:text-content-primary hover:bg-surface-hover cursor-pointer"><RefreshCw size={15} className={fns.isFetching ? 'animate-spin' : ''} /></button>
            </>}
          </div>
          <p className="mt-2 mb-4 text-xs text-content-tertiary">zip 으로 만든 코드를 등록해 두고, 실행할 때마다 새 격리 환경에서 돌린 뒤 폐기합니다. 네트워크는 차단되고 실행 기록은 {info?.limits.retention_days ?? 30}일 보관됩니다.</p>

          {infoLoading ? (
            <div className="py-16 flex items-center justify-center text-sm text-content-muted"><Loader2 size={16} className="animate-spin mr-2" /> 불러오는 중...</div>
          ) : !info?.enabled ? (
            <div role="status" className="rounded-xl border border-border py-14 text-center text-sm text-content-secondary">Functions 기능이 꺼져 있습니다.<div className="mt-1 text-xs text-content-tertiary">관리자가 FUNCTION_ENABLED 를 켜야 합니다.</div></div>
          ) : !info.allowed ? (
            <div role="status" className="rounded-xl border border-border py-14 text-center text-sm text-content-secondary">Functions 를 사용할 권한이 없습니다.<div className="mt-1 text-xs text-content-tertiary">관리자에게 사용 허용을 요청하세요.</div></div>
          ) : (
            <>
              <div role="tablist" className="flex gap-1 border-b border-border mb-4">{tabBtn('functions', '함수')}{tabBtn('runs', '실행 이력')}{tabBtn('triggers', '트리거')}</div>

              {tab === 'functions' && (
                fns.isLoading ? <div className="py-12 flex items-center justify-center text-sm text-content-muted"><Loader2 size={16} className="animate-spin mr-2" /> 불러오는 중...</div>
                : fns.isError ? <div role="alert" className="py-10 text-center text-sm text-accent-red">{driveError(fns.error, '함수 목록을 불러오지 못했습니다')}</div>
                : (fns.data ?? []).length === 0 ? (
                  <div className="rounded-xl border border-dashed border-border py-14 text-center text-sm text-content-muted">
                    등록된 함수가 없습니다.
                    <div className="mt-3"><button onClick={() => setCreating(true)} className="px-3 py-1.5 rounded-lg text-sm border border-border bg-transparent text-content-primary hover:bg-surface-hover cursor-pointer">첫 함수 등록하기</button></div>
                  </div>
                ) : (
                  <div className="rounded-xl border border-border overflow-hidden">
                    <table className="w-full border-collapse" aria-label="함수 목록">
                      <thead><tr className="border-b border-border"><th className={th}>이름</th><th className={th}>런타임</th><th className={th}>버전</th><th className={th}>최근 실행</th><th className={`${th} text-right`}>수정일시</th></tr></thead>
                      <tbody>
                        {(fns.data ?? []).map((f) => (
                          <tr key={f.id} onClick={() => navigate(`/workflow/functions/${f.id}`)} className="border-b last:border-b-0 border-border hover:bg-surface-hover cursor-pointer">
                            <td className="px-4 py-3">
                              <button onClick={(e) => { e.stopPropagation(); navigate(`/workflow/functions/${f.id}`) }} className="border-none bg-transparent p-0 text-sm font-medium text-content-primary cursor-pointer hover:underline text-left">{f.name}</button>
                              {f.disabled && <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] bg-accent-red/15 text-accent-red">중지됨</span>}
                              {f.description && <div className="text-xs text-content-tertiary truncate max-w-[320px]">{f.description}</div>}
                            </td>
                            <td className="px-4 py-3 text-xs text-content-secondary">{f.runtime}</td>
                            <td className="px-4 py-3 text-xs text-content-secondary">v{f.latest_version}</td>
                            <td className="px-4 py-3"><StatusBadge status={f.last_run?.status} /></td>
                            <td className="px-4 py-3 text-right text-xs text-content-tertiary whitespace-nowrap">{f.updated_at ? formatDateTimeMinute(f.updated_at) : ''}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )
              )}

              {tab === 'triggers' && (
                triggers.isLoading ? <div className="py-12 flex items-center justify-center text-sm text-content-muted"><Loader2 size={16} className="animate-spin mr-2" /> 불러오는 중...</div>
                : triggers.isError ? <div role="alert" className="py-10 text-center text-sm text-accent-red">{driveError(triggers.error, '트리거를 불러오지 못했습니다')}</div>
                : (triggers.data ?? []).length === 0 ? <div className="rounded-xl border border-dashed border-border py-14 text-center text-sm text-content-muted">등록된 트리거가 없습니다<div className="mt-1 text-xs text-content-tertiary">함수 상세에서 예약이나 웹훅을 추가하세요</div></div>
                : <ul className="m-0 px-4 list-none rounded-xl border border-border" aria-label="트리거 목록">{(triggers.data ?? []).map((t) => <TriggerRow key={t.id} t={t} fnName={names[t.function_id]} onChanged={() => qc.invalidateQueries({ queryKey: ['fn-all-triggers'] })} />)}</ul>
              )}

              {tab === 'runs' && (
                <>
                  <div className="flex items-center gap-2 mb-3">
                    <select aria-label="함수 필터" value={fnFilter} onChange={(e) => setFnFilter(e.target.value)} className={select}>
                      <option value="">모든 함수</option>
                      {(fns.data ?? []).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
                    </select>
                    <select aria-label="상태 필터" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className={select}>
                      <option value="">모든 상태</option>
                      {(Object.keys(STATUS_LABEL) as RunStatus[]).map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
                    </select>
                  </div>
                  {runs.isLoading ? <div className="py-12 flex items-center justify-center text-sm text-content-muted"><Loader2 size={16} className="animate-spin mr-2" /> 불러오는 중...</div>
                  : runs.isError ? <div role="alert" className="py-10 text-center text-sm text-accent-red">{driveError(runs.error, '실행 이력을 불러오지 못했습니다')}</div>
                  : (runs.data ?? []).length === 0 ? <div className="rounded-xl border border-border py-14 text-center text-sm text-content-muted">실행 기록이 없습니다</div>
                  : (
                    <div className="rounded-xl border border-border overflow-hidden">
                      <table className="w-full border-collapse" aria-label="실행 이력">
                        <thead><tr className="border-b border-border"><th className={th}>요청 시각</th><th className={th}>함수</th><th className={th}>버전</th><th className={th}>상태</th><th className={th}>트리거</th><th className={`${th} text-right`}>소요</th></tr></thead>
                        <tbody>
                          {(runs.data ?? []).map((r) => (
                            <tr key={r.id} onClick={() => setOpenRun(r.id)} className="border-b last:border-b-0 border-border hover:bg-surface-hover cursor-pointer">
                              <td className="px-4 py-2.5 text-xs text-content-secondary whitespace-nowrap">{r.queued_at ? formatDateTimeMinute(r.queued_at) : ''}</td>
                              <td className="px-4 py-2.5 text-sm text-content-primary">
                                <button onClick={(e) => { e.stopPropagation(); setOpenRun(r.id) }} className="border-none bg-transparent p-0 text-sm text-content-primary cursor-pointer hover:underline text-left">{names[r.function_id] ?? r.function_id.slice(0, 8)}</button>
                              </td>
                              <td className="px-4 py-2.5 text-xs text-content-secondary">v{r.version}</td>
                              <td className="px-4 py-2.5"><StatusBadge status={r.status} /></td>
                              <td className="px-4 py-2.5 text-xs text-content-secondary">{r.trigger}</td>
                              <td className="px-4 py-2.5 text-right text-xs text-content-tertiary">{formatDuration(r.duration_ms)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </div>
      </main>
      {creating && <CreateFunctionDialog onClose={() => setCreating(false)} onCreated={(fn) => { setCreating(false); refresh(); navigate(`/workflow/functions/${fn.id}`) }} />}
      {openRun && <RunDetailDialog runId={openRun} functionName={names[(runs.data ?? []).find((r) => r.id === openRun)?.function_id ?? '']} onClose={() => { setOpenRun(null); refresh() }} />}
    </div>
  )
}

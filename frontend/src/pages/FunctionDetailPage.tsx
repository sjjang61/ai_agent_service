import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, HardDrive, Loader2, Play, Trash2, Upload } from 'lucide-react'
import { useRef } from 'react'
import IconBar from '../components/layout/IconBar'
import Sidebar from '../components/chat/Sidebar'
import { ACTIVE, formatDuration, functionsApi, uploadPackageToDrive, type RunDetail, type RunSummary } from '../api/functions'
import { driveError } from '../api/drive'
import DriveFilePickerDialog from '../components/drive/DriveFilePickerDialog'
import JsonBlock from '../components/functions/JsonBlock'
import RunDetailDialog from '../components/functions/RunDetailDialog'
import TriggersSection from '../components/functions/TriggersSection'
import StatusBadge from '../components/functions/StatusBadge'
import { formatDateTimeMinute } from '../utils/time'
import { formatBytes } from '../components/drive/driveUtils'

const card = 'rounded-xl border border-border bg-surface-primary p-4'
const h2 = 'm-0 mb-3 text-sm font-semibold text-content-primary'
const input = 'px-2.5 py-1.5 rounded-lg border border-border bg-surface-secondary text-xs text-content-primary'
const btn = 'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border border-border bg-surface-secondary text-content-primary hover:bg-surface-hover cursor-pointer disabled:opacity-50'

/** 함수 상세: 테스트 실행, 버전·별칭, 시크릿, 최근 실행, 삭제 */
export default function FunctionDetailPage() {
  const { functionId = '' } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [openRun, setOpenRun] = useState<string | null>(null)
  const [msg, setMsg] = useState<{ text: string; error?: boolean } | null>(null)
  const say = (text: string, error = false) => setMsg({ text, error })

  const { data: fn, isLoading, isError, error } = useQuery({ queryKey: ['fn', functionId], queryFn: () => functionsApi.get(functionId), retry: false })
  const recent = useQuery({ queryKey: ['fn-runs', functionId, 'recent'], queryFn: () => functionsApi.runs({ function_id: functionId, limit: 10 }), enabled: !!fn, retry: false,
    refetchInterval: (q) => (q.state.data?.some((r) => ACTIVE.includes(r.status)) ? 2500 : false) })
  const refresh = () => { qc.invalidateQueries({ queryKey: ['fn', functionId] }); qc.invalidateQueries({ queryKey: ['fn-runs'] }); qc.invalidateQueries({ queryKey: ['fn-list'] }) }

  // ── 테스트 실행 ──
  const [eventText, setEventText] = useState('{}')
  const [ref, setRef] = useState('latest')
  const [result, setResult] = useState<{ run: RunSummary | RunDetail; done: boolean } | null>(null)
  let eventErr: string | null = null
  try { JSON.parse(eventText || '{}') } catch (e) { eventErr = `JSON 형식이 올바르지 않습니다: ${(e as Error).message}` }
  const invoke = useMutation({
    mutationFn: () => functionsApi.invoke(functionId, JSON.parse(eventText || '{}'), { ref, wait: true }),
    onSuccess: (r) => { setResult(r); refresh() },
    onError: (e) => { setResult(null); say(driveError(e, '실행하지 못했습니다'), true) },
  })

  // ── 버전 ──
  const [picking, setPicking] = useState(false)
  const [uploading, setUploading] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const addVersion = async (nodeId: string) => {
    try {
      const r = await functionsApi.addVersion(functionId, nodeId)
      say(r.created ? `v${r.version.version} 을(를) 만들었습니다` : `내용이 이전 버전(v${r.version.version})과 같아 새 버전을 만들지 않았습니다`)
      refresh()
    } catch (e) { say(driveError(e, '버전을 만들지 못했습니다'), true) }
  }
  const uploadVersion = async (file: File) => {
    setUploading(true)
    try { await addVersion(await uploadPackageToDrive(file, () => undefined)) } catch (e) { say(e instanceof Error && !('response' in e) ? e.message : driveError(e, '올리지 못했습니다'), true) } finally { setUploading(false) }
  }
  const [aliasName, setAliasName] = useState('')
  const [aliasVersion, setAliasVersion] = useState('')
  const setAlias = useMutation({
    mutationFn: () => functionsApi.setAlias(functionId, aliasName.trim(), Number(aliasVersion || fn?.latest_version)),
    onSuccess: () => { setAliasName(''); say('별칭을 저장했습니다'); refresh() },
    onError: (e) => say(driveError(e, '별칭을 저장하지 못했습니다'), true),
  })
  const delAlias = useMutation({ mutationFn: (a: string) => functionsApi.removeAlias(functionId, a), onSuccess: refresh, onError: (e) => say(driveError(e, '별칭을 지우지 못했습니다'), true) })

  // ── 시크릿 ──
  const [secKey, setSecKey] = useState('')
  const [secVal, setSecVal] = useState('')
  const putSecret = useMutation({
    mutationFn: () => functionsApi.putSecret(functionId, secKey.trim(), secVal),
    onSuccess: () => { setSecKey(''); setSecVal(''); say('시크릿을 저장했습니다 (값은 다시 볼 수 없습니다)'); refresh() },
    onError: (e) => say(driveError(e, '시크릿을 저장하지 못했습니다'), true),
  })
  const delSecret = useMutation({ mutationFn: (k: string) => functionsApi.removeSecret(functionId, k), onSuccess: refresh, onError: (e) => say(driveError(e, '시크릿을 지우지 못했습니다'), true) })

  const del = async () => {
    if (!confirm(`'${fn?.name}' 함수를 삭제할까요?\n등록된 버전·시크릿을 쓸 수 없게 되고, 실행 기록은 보관 기간 후 정리됩니다.`)) return
    try { await functionsApi.remove(functionId); qc.invalidateQueries({ queryKey: ['fn-list'] }); navigate('/workflow') } catch (e) { say(driveError(e, '삭제하지 못했습니다'), true) }
  }

  const aliasesByVersion = useMemo(() => {
    const m: Record<number, string[]> = {}
    for (const [a, v] of Object.entries(fn?.aliases ?? {})) (m[v] ??= []).push(a)
    return m
  }, [fn?.aliases])
  const latestCfg = fn?.versions[0]?.config

  return (
    <div className="flex h-screen bg-surface-primary overflow-hidden">
      <IconBar />
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-auto">
        <div className="max-w-[960px] mx-auto px-6 pt-10 pb-24 space-y-4">
          <button onClick={() => navigate('/workflow')} className="flex items-center gap-1 px-0 py-1 text-sm border-none bg-transparent text-content-secondary hover:text-content-primary cursor-pointer"><ArrowLeft size={15} /> Workflow</button>
          {isLoading ? <div className="py-16 flex items-center justify-center text-sm text-content-muted"><Loader2 size={16} className="animate-spin mr-2" /> 불러오는 중...</div>
          : isError || !fn ? <div role="alert" className="py-12 text-center text-sm text-accent-red">{driveError(error, '함수를 불러오지 못했습니다')}</div>
          : (
            <>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="m-0 text-xl font-semibold text-content-primary">{fn.name}</h1>
                  <span className="px-2 py-0.5 rounded-full text-[11px] bg-surface-tertiary text-content-secondary">{fn.runtime}</span>
                  <span className="text-xs text-content-tertiary">latest v{fn.latest_version}</span>
                  {fn.disabled && <span className="px-2 py-0.5 rounded-full text-[11px] bg-accent-red/15 text-accent-red">관리자가 중지함</span>}
                </div>
                {fn.description && <p className="mt-1 mb-0 text-sm text-content-secondary">{fn.description}</p>}
                {fn.disabled && <p role="alert" className="mt-2 mb-0 text-xs text-accent-red">이 함수는 실행할 수 없습니다{fn.disabled_reason ? `: ${fn.disabled_reason}` : ''}</p>}
                {latestCfg && <p className="mt-2 mb-0 text-xs text-content-tertiary">핸들러 {latestCfg.handler} · 제한 시간 {latestCfg.timeout_seconds}초 · 메모리 {latestCfg.memory_mb}MB · 네트워크 차단{Object.keys(latestCfg.env).length > 0 && ` · 환경변수 ${Object.keys(latestCfg.env).join(', ')}`}</p>}
              </div>
              {msg && <p role={msg.error ? 'alert' : 'status'} className={`m-0 text-xs ${msg.error ? 'text-accent-red' : 'text-accent-green'}`}>{msg.text}</p>}

              <section className={card} aria-label="테스트 실행">
                <h2 className={h2}>테스트 실행</h2>
                <label className="block text-xs text-content-secondary">입력(event) JSON
                  <textarea value={eventText} onChange={(e) => setEventText(e.target.value)} rows={4} spellCheck={false} aria-invalid={!!eventErr}
                    className="mt-1 w-full p-2.5 rounded-lg border border-border bg-surface-secondary text-xs font-mono text-content-primary" />
                </label>
                {eventErr && <p role="alert" className="m-0 mt-1 text-xs text-accent-red">{eventErr}</p>}
                <div className="mt-2 flex items-center gap-2">
                  <select aria-label="실행할 버전" value={ref} onChange={(e) => setRef(e.target.value)} className={input}>
                    <option value="latest">latest (v{fn.latest_version})</option>
                    {Object.keys(fn.aliases).filter((a) => a !== 'latest').map((a) => <option key={a} value={a}>{a} (v{fn.aliases[a]})</option>)}
                    {fn.versions.map((v) => <option key={v.version} value={String(v.version)}>v{v.version}</option>)}
                  </select>
                  <button onClick={() => { setMsg(null); setResult(null); invoke.mutate() }} disabled={!!eventErr || invoke.isPending || fn.disabled} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border-none bg-accent-primary text-white cursor-pointer disabled:opacity-50">
                    {invoke.isPending ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} 실행
                  </button>
                </div>
                {result && (
                  <div className="mt-3 space-y-2" aria-live="polite">
                    <div className="flex items-center gap-2 text-xs"><StatusBadge status={result.run.status} /><span className="text-content-tertiary">{formatDuration(result.run.duration_ms)}</span>
                      <button onClick={() => setOpenRun(result.run.id)} className="ml-auto border-none bg-transparent p-0 text-xs text-accent-primary cursor-pointer hover:underline">상세·로그 보기</button></div>
                    {!result.done && <p className="m-0 text-xs text-content-tertiary">아직 실행 중입니다. 끝나면 실행 이력에서 확인하세요.</p>}
                    {result.done && result.run.status === 'succeeded' && <JsonBlock label="결과" value={(result.run as RunDetail).result} empty="null" />}
                    {result.done && result.run.error && <div role="alert" className="p-3 rounded-lg border border-accent-red/40 bg-accent-red/10 text-xs text-accent-red"><b>{result.run.error.type}</b><div className="whitespace-pre-wrap break-words">{result.run.error.message}</div></div>}
                  </div>
                )}
              </section>

              <section className={card} aria-label="버전과 별칭">
                <div className="flex items-center gap-2 mb-3">
                  <h2 className="flex-1 m-0 text-sm font-semibold text-content-primary">버전과 별칭</h2>
                  <button onClick={() => setPicking(true)} className={btn}><HardDrive size={13} /> Drive 에서 새 버전</button>
                  <button onClick={() => fileInput.current?.click()} disabled={uploading} className={btn}>{uploading ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />} 올려서 새 버전</button>
                  <input ref={fileInput} type="file" accept=".zip,application/zip" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadVersion(f); e.target.value = '' }} />
                </div>
                <table className="w-full border-collapse text-xs" aria-label="버전 목록">
                  <thead><tr className="border-b border-border text-content-secondary"><th className="py-2 text-left font-medium">버전</th><th className="text-left font-medium">별칭</th><th className="text-left font-medium">생성일시</th><th className="text-left font-medium">파일</th><th className="text-left font-medium">핸들러</th><th className="text-right font-medium">제한</th></tr></thead>
                  <tbody>
                    {fn.versions.map((v) => (
                      <tr key={v.version} className="border-b last:border-b-0 border-border">
                        <td className="py-2 text-content-primary font-medium">v{v.version}{v.version === fn.latest_version && <span className="ml-1.5 text-[10px] text-content-tertiary">latest</span>}</td>
                        <td>{(aliasesByVersion[v.version] ?? []).filter((a) => a !== 'latest').map((a) => (
                          <span key={a} className="inline-flex items-center gap-1 mr-1 px-1.5 py-0.5 rounded bg-surface-tertiary text-content-secondary">{a}
                            <button onClick={() => delAlias.mutate(a)} aria-label={`별칭 ${a} 삭제`} className="border-none bg-transparent p-0 text-content-muted hover:text-accent-red cursor-pointer">×</button></span>))}</td>
                        <td className="text-content-tertiary whitespace-nowrap">{v.created_at ? formatDateTimeMinute(v.created_at) : ''}</td>
                        <td className="text-content-tertiary" title={v.source_ref?.drive_path}>{v.file_count}개 · {formatBytes(v.unpacked_bytes)}</td>
                        <td className="text-content-tertiary">{v.config.handler}</td>
                        <td className="text-right text-content-tertiary">{v.config.timeout_seconds}s · {v.config.memory_mb}MB</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="mt-3 flex items-center gap-2">
                  <input value={aliasName} onChange={(e) => setAliasName(e.target.value)} placeholder="별칭 (예: prod)" aria-label="별칭 이름" className={`${input} w-36`} />
                  <select aria-label="별칭이 가리킬 버전" value={aliasVersion} onChange={(e) => setAliasVersion(e.target.value)} className={input}>
                    <option value="">latest (v{fn.latest_version})</option>
                    {fn.versions.map((v) => <option key={v.version} value={v.version}>v{v.version}</option>)}
                  </select>
                  <button onClick={() => setAlias.mutate()} disabled={!aliasName.trim() || setAlias.isPending} className={btn}>별칭 지정</button>
                  <span className="text-[11px] text-content-tertiary">예약·API 가 별칭을 가리키면 새 버전이 나와도 의도치 않게 바뀌지 않습니다</span>
                </div>
              </section>

              <section className={card} aria-label="시크릿">
                <h2 className={h2}>시크릿 <span className="font-normal text-xs text-content-tertiary">실행할 때 환경변수로만 주입되고 값은 다시 볼 수 없습니다</span></h2>
                {fn.secrets.length === 0 ? <p className="m-0 mb-2 text-xs text-content-muted">등록된 시크릿이 없습니다</p> : (
                  <ul className="m-0 mb-3 p-0 list-none space-y-1">
                    {fn.secrets.map((k) => <li key={k} className="flex items-center gap-2 text-xs"><code className="font-mono text-content-primary">{k}</code><span className="text-content-muted">••••••••</span>
                      <button onClick={() => delSecret.mutate(k)} aria-label={`시크릿 ${k} 삭제`} className="ml-auto border-none bg-transparent text-content-muted hover:text-accent-red cursor-pointer"><Trash2 size={13} /></button></li>)}
                  </ul>
                )}
                <div className="flex items-center gap-2">
                  <input value={secKey} onChange={(e) => setSecKey(e.target.value)} placeholder="API_KEY" aria-label="시크릿 이름" className={`${input} w-40 font-mono`} />
                  <input value={secVal} onChange={(e) => setSecVal(e.target.value)} type="password" autoComplete="new-password" placeholder="값" aria-label="시크릿 값" className={`${input} flex-1`} />
                  <button onClick={() => putSecret.mutate()} disabled={!secKey.trim() || !secVal || putSecret.isPending} className={btn}>저장</button>
                </div>
              </section>

              <TriggersSection fn={fn} />

              <section className={card} aria-label="최근 실행">
                <h2 className={h2}>최근 실행</h2>
                {(recent.data ?? []).length === 0 ? <p className="m-0 text-xs text-content-muted">실행 기록이 없습니다</p> : (
                  <ul className="m-0 p-0 list-none">
                    {(recent.data ?? []).map((r) => (
                      <li key={r.id}><button onClick={() => setOpenRun(r.id)} className="w-full flex items-center gap-3 px-2 py-2 rounded-lg border-none bg-transparent text-left hover:bg-surface-hover cursor-pointer text-xs">
                        <StatusBadge status={r.status} /><span className="text-content-secondary">v{r.version}</span><span className="text-content-tertiary">{r.trigger}</span>
                        <span className="ml-auto text-content-tertiary">{formatDuration(r.duration_ms)}</span><span className="w-32 text-right text-content-tertiary">{r.queued_at ? formatDateTimeMinute(r.queued_at) : ''}</span></button></li>
                    ))}
                  </ul>
                )}
              </section>

              <div className="pt-2"><button onClick={del} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border border-accent-red/50 bg-transparent text-accent-red hover:bg-accent-red/10 cursor-pointer"><Trash2 size={13} /> 함수 삭제</button></div>
            </>
          )}
        </div>
      </main>
      {picking && <DriveFilePickerDialog title="새 버전 패키지(zip) 선택" confirmLabel="선택" extensions={['zip']} maxSelect={1} onPick={(nodes) => { setPicking(false); if (nodes[0]) addVersion(nodes[0].id) }} onClose={() => setPicking(false)} />}
      {openRun && <RunDetailDialog runId={openRun} functionName={fn?.name} onClose={() => { setOpenRun(null); refresh() }} />}
    </div>
  )
}

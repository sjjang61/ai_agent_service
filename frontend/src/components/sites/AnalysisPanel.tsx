import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { siteProfilesApi, siteSpecOf, verticalSpecOf, type AnalysisRun, type FlowResult, type SiteSpec, type VerticalSpec } from '../../api/siteProfiles'
import BrowserShots from '../chat/BrowserShots'
import LoginRequestCard from '../chat/LoginRequestCard'
import { formatDuration } from '../chat/taskItems'
import { errorText, inputCls, primaryBtn } from '../skills/common'
import DiffView from './DiffView'
import { Field, TextArea, secondaryBtn } from './fields'

const FLOW_STATUS: Record<FlowResult['status'], { label: string; cls: string }> = {
  reached: { label: '도달', cls: 'text-green-600' },
  failed: { label: '막힘', cls: 'text-red-500' },
  missing: { label: '보고 없음', cls: 'text-red-500' },
  skipped: { label: '건너뜀', cls: 'text-content-tertiary' },
  untested: { label: '시험 안 함', cls: 'text-content-tertiary' },
  excluded: { label: '사이트에서 제외', cls: 'text-content-tertiary' },
}

const specFilled = (s: SiteSpec) => s.entry.length > 0 || s.menus.length > 0 || Object.keys(s.inputs).length > 0 || s.flow.length > 0 || !!s.stop_point
/** 비교용 문자열: 저장된 값과 에이전트가 만든 값의 키 순서가 달라도 같은 내용이면 차이로 보이지 않게 정규화한다 */
const prettySpec = (s: SiteSpec) => {
  if (!specFilled(s)) return ''
  const inputs = Object.fromEntries(Object.keys(s.inputs).sort().map((k) => [k, { how: s.inputs[k].how, param: s.inputs[k].param }]))
  return JSON.stringify({
    entry: s.entry.map((e) => ({ label: e.label, url: e.url })),
    menus: s.menus.map((m) => ({ name: m.name, path: m.path, url: m.url })),
    inputs,
    flow: s.flow.map((f) => ({ key: f.key, how: f.how, url: f.url })),
    stop_point: s.stop_point,
  }, null, 2)
}

const STATUS: Record<AnalysisRun['status'], { label: string; cls: string }> = {
  running: { label: '실행 중', cls: 'bg-blue-500/15 text-blue-500' },
  succeeded: { label: '완료', cls: 'bg-green-500/15 text-green-600' },
  failed: { label: '실패', cls: 'bg-red-500/15 text-red-500' },
  cancelled: { label: '중단됨', cls: 'bg-surface-active text-content-secondary' },
}

interface Props {
  name: string
  vertical: string | null
  domains: string
  /** 편집 중인 예외·주의와 구조 (분석 때 "현재 값"으로 넘기고, 초안과 비교한다) */
  currentBody: string
  currentSpec: SiteSpec
  /** 분야가 정의한 입력값·표준 단계 */
  verticalSpec?: Partial<VerticalSpec>
  onLoadDraft: (body: string, spec: SiteSpec) => void
  /** 재현 검증을 통과한 초안을 검증됨으로 저장 */
  onSaveVerified: (body: string, spec: SiteSpec) => void
  saving: boolean
  canSave: boolean
}

export default function AnalysisPanel({ name, vertical, domains, currentBody, currentSpec, verticalSpec, onLoadDraft, onSaveVerified, saving, canSave }: Props) {
  const qc = useQueryClient()
  const firstDomain = domains.split(',')[0]?.trim()
  const [startUrl, setStartUrl] = useState(firstDomain ? `https://${firstDomain}` : '')
  const [scenario, setScenario] = useState('')
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [handoff, setHandoff] = useState(false)
  const [clean, setClean] = useState(false)
  const vspec = verticalSpecOf(verticalSpec)
  const hasFlow = vspec.flow.length > 0
  const editorFilled = specFilled(currentSpec) || !!currentBody.trim()
  const [runId, setRunId] = useState<string | null>(null)
  const [error, setError] = useState('')

  const runs = useQuery({
    queryKey: ['site-analysis-runs', name],
    queryFn: async () => (await siteProfilesApi.analysisRuns(name.trim() || undefined)).data,
    enabled: !!name.trim(),
  })
  // 처음 열면 이 사이트의 가장 최근 실행을 보여 준다 (새로고침해도 진행 중인 분석을 이어서 본다)
  useEffect(() => {
    if (runId === null && runs.data && runs.data.length > 0) {
      setRunId(runs.data[0].id)
      setScenario((s) => s || runs.data![0].scenario)
      setStartUrl((u) => u || runs.data![0].start_url)
    }
  }, [runs.data, runId])

  const run = useQuery({
    queryKey: ['site-analysis-run', runId],
    queryFn: async () => (await siteProfilesApi.analysisRun(runId!)).data,
    enabled: !!runId,
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 2000 : false),
  })
  const r = run.data
  const running = r?.status === 'running'
  const refreshList = () => qc.invalidateQueries({ queryKey: ['site-analysis-runs', name] })

  const start = useMutation({
    mutationFn: async (input: { mode: 'analyze' | 'verify'; draft?: string; spec?: SiteSpec; base?: string }) =>
      (await siteProfilesApi.startAnalysis({
        mode: input.mode, name: name.trim(), vertical, start_url: startUrl.trim(), scenario: scenario.trim(),
        draft_body: input.draft, draft_spec: input.mode === 'verify' ? input.spec : currentSpec, current_body: currentBody, base_run_id: input.base,
        inputs: Object.fromEntries(Object.entries(inputs).filter(([, v]) => v.trim())),
        captcha_handoff: handoff,
        clean_session: clean,
      })).data,
    onSuccess: (data) => { setError(''); setRunId(data.id); qc.setQueryData(['site-analysis-run', data.id], data); refreshList() },
    onError: (e) => setError(errorText(e, '시작하지 못했습니다')),
  })
  const cancel = useMutation({
    mutationFn: () => siteProfilesApi.cancelAnalysis(runId!),
    onSuccess: (data) => { qc.setQueryData(['site-analysis-run', data.data.id], data.data); refreshList() },
    onError: (e) => setError(errorText(e, '중단하지 못했습니다')),
  })
  useEffect(() => { if (r && r.status !== 'running') refreshList() }, [r?.status]) // eslint-disable-line react-hooks/exhaustive-deps

  const ready = !!name.trim() && !!startUrl.trim() && (scenario.trim().length >= 5 || hasFlow)
  const busy = start.isPending || running

  return (
    <div className="space-y-3">
      <p className="text-[13px] text-content-secondary">
        브라우저 에이전트가 분야의 입력값을 이 사이트에서 하나씩 넣어 보고, 표준 단계를 따라가며 진입 주소·메뉴·입력 방법을 정리해 초안을 만듭니다. <b>읽기만</b> 하며 로그인·장바구니·좌석 선택·예약·결제는 실행하지 않습니다.
        데스크톱 앱에 연결돼 있으면 내 브라우저에서, 아니면 서버 브라우저에서 실행됩니다.
      </p>
      {error && <div className="text-[13px] text-red-500">{error}</div>}
      <Field label="시작 주소">
        <input value={startUrl} onChange={(e) => setStartUrl(e.target.value)} className={inputCls} placeholder="https://flight.naver.com" />
      </Field>
      {vspec.inputs.length > 0 ? (
        <div className="space-y-1.5">
          <div className="text-[13px] font-medium text-content-primary">이번에 쓸 입력값</div>
          <p className="text-xs text-content-tertiary">비워 두면 분야에 정의된 샘플 값을 씁니다. 분석과 재현 검증에 같은 값을 쓰세요.</p>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
            {vspec.inputs.map((i) => (
              <label key={i.key} className="flex items-center gap-2 text-[12.5px] text-content-secondary">
                <span className="w-[84px] flex-shrink-0 truncate" title={i.key}>{i.label}{i.required ? ' *' : ''}</span>
                <input value={inputs[i.key] ?? ''} onChange={(e) => setInputs((v) => ({ ...v, [i.key]: e.target.value }))} placeholder={vspec.sample[i.key] || i.example} className={`${inputCls} !py-1.5 !text-[13px]`} />
              </label>
            ))}
          </div>
        </div>
      ) : (
        <p className="text-xs text-content-tertiary">이 분야에는 아직 입력값·표준 단계가 정의되어 있지 않습니다. 분야를 고르고 구조를 정의하면 입력값별로 분석·검증됩니다. 지금은 시나리오 문장으로 수행합니다.</p>
      )}
      <Field label={hasFlow ? '추가 시나리오 (선택)' : '시나리오'} hint={hasFlow ? '비우면 표준 단계를 위 입력값으로 처음부터 끝까지 수행합니다. 특정 상황(예: 필터 적용)을 더 보고 싶을 때만 적으세요.' : '실제 작업처럼 구체적으로 적으세요. 분석과 재현 검증에 같은 시나리오를 씁니다.'}>
        <TextArea value={scenario} onChange={setScenario} rows={2} placeholder={hasFlow ? '' : '예: 진라면 5개입을 검색해 낮은 가격순으로 정렬하고 상위 결과의 가격을 확인'} />
      </Field>
      <label className="flex items-start gap-2 text-[13px] text-content-primary cursor-pointer">
        <input type="checkbox" checked={clean} onChange={(e) => { setClean(e.target.checked); if (e.target.checked) setHandoff(false) }} className="mt-0.5" />
        <span>
          깨끗한 환경에서 실행 (내 로그인·이전 검색 상태 없이)
          <span className="block text-xs text-content-tertiary">
            내 앱 브라우저 대신 서버의 깨끗한 브라우저(sandbox)에서 실행합니다. 내 로그인, 최근 본 숙소·검색 기록, 이전에 고른 인원·필터가 분석 결과에 섞이지 않습니다. 대신 서버 브라우저는 캡차에 더 자주 걸릴 수 있고, 걸리면 넘길 수 없어 거기까지의 결과로 끝납니다. 이번 분석 전에 서버 브라우저의 이전 세션은 초기화됩니다.
          </span>
        </span>
      </label>
      <label className={`flex items-start gap-2 text-[13px] text-content-primary ${clean ? 'opacity-50' : 'cursor-pointer'}`}>
        <input type="checkbox" checked={handoff} disabled={clean} onChange={(e) => setHandoff(e.target.checked)} className="mt-0.5" />
        <span>
          캡차(로봇 확인)가 나오면 나에게 넘기기
          <span className="block text-xs text-content-tertiary">
            켜면 캡차 화면에서 멈추고 아래에 카드가 나타납니다. 브라우저에서 직접 해결한 뒤 ‘해결 완료’를 누르면 이어서 진행합니다. 화면 앞에 있을 때만 켜세요. 끄면 캡차에서 거기까지의 결과로 끝납니다. 로그인·장바구니·결제 같은 쓰기 동작은 이 옵션과 상관없이 실행되지 않습니다.
          </span>
        </span>
      </label>
      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={() => start.mutate({ mode: 'analyze' })} disabled={!ready || busy} className={primaryBtn}>
          {start.isPending ? '시작 중…' : '분석 실행'}
        </button>
        <button
          onClick={() => start.mutate({ mode: 'verify', draft: currentBody, spec: currentSpec })}
          disabled={!ready || busy || !editorFilled}
          title={editorFilled ? '지금 편집기의 구조·요령으로 표준 단계를 다시 수행해 봅니다' : '편집기에 구조나 요령이 있어야 검증할 수 있습니다'}
          className={secondaryBtn}
        >
          편집기의 내용 검증
        </button>
        {running && <button onClick={() => cancel.mutate()} disabled={cancel.isPending} className={secondaryBtn}>중단</button>}
      </div>

      {r && (
        <div className="border border-border rounded-[var(--radius-lg)] p-3 space-y-3 bg-surface-secondary">
          {r.captcha_handoff && <LoginRequestCard conversationId={`siteanalysis:${r.id}`} active={running} />}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[13px] font-medium text-content-primary">{r.mode === 'analyze' ? '분석' : '재현 검증'}</span>
            <span className={`px-1.5 py-0.5 rounded-full text-[11px] font-medium ${STATUS[r.status].cls}`}>{STATUS[r.status].label}</span>
            <span className="text-xs text-content-tertiary truncate flex-1" title={r.scenario}>{r.scenario}</span>
          </div>
          {r.error && <div className="text-[13px] text-red-500">{r.error}</div>}

          {r.steps.length > 0 && (
            <ol className="space-y-0.5 max-h-[200px] overflow-y-auto text-[12.5px]">
              {r.steps.map((s, i) => (
                <li key={s.id ?? i} className="flex gap-2 items-baseline">
                  <span className={`w-3 flex-shrink-0 ${s.ok === false ? 'text-red-500' : s.ok ? 'text-green-600' : 'text-content-muted'}`}>{s.ok === false ? '✗' : s.ok ? '✓' : '…'}</span>
                  <span className="text-content-primary flex-1 min-w-0 truncate" title={s.brief || s.desc}>{s.desc}</span>
                  {s.t0 && s.t1 ? <span className="text-content-tertiary flex-shrink-0">{formatDuration(s.t1 - s.t0)}</span> : null}
                </li>
              ))}
            </ol>
          )}
          {r.browser_run && <BrowserShots run={r.browser_run} running={running} live={running} conversationId={null} size="md" />}

          {r.mode === 'analyze' && r.status === 'succeeded' && (r.draft_body || r.draft_spec) && (() => {
            const dSpec = siteSpecOf(r.draft_spec)
            const dBody = r.draft_body ?? ''
            return (
              <div className="space-y-2">
                <div className="text-[13px] font-medium text-content-primary">만들어진 초안 {specFilled(currentSpec) || currentBody.trim() ? '(편집기 내용과 비교)' : ''}</div>
                <div className="text-xs font-medium text-content-secondary">구조</div>
                {specFilled(currentSpec) ? <DiffView before={prettySpec(currentSpec)} after={prettySpec(dSpec)} empty="편집기의 구조와 같습니다" /> : (
                  <pre className="p-2.5 bg-surface-primary border border-border rounded-[var(--radius-md)] text-[12.5px] whitespace-pre-wrap break-words max-h-[320px] overflow-y-auto">{prettySpec(dSpec) || '(구조 없음)'}</pre>
                )}
                {dBody && (
                  <>
                    <div className="text-xs font-medium text-content-secondary">예외·주의</div>
                    {currentBody.trim() ? <DiffView before={currentBody} after={dBody} empty="편집기의 내용과 같습니다" /> : (
                      <pre className="p-2.5 bg-surface-primary border border-border rounded-[var(--radius-md)] text-[12.5px] whitespace-pre-wrap break-words max-h-[200px] overflow-y-auto">{dBody}</pre>
                    )}
                  </>
                )}
                {r.answer && <p className="text-xs text-content-secondary whitespace-pre-wrap"><b>분석 메모</b> {r.answer}</p>}
                <div className="flex gap-2 flex-wrap">
                  <button onClick={() => start.mutate({ mode: 'verify', draft: dBody, spec: dSpec, base: r.id })} disabled={busy || !ready} className={primaryBtn}>이 초안으로 재현 검증</button>
                  <button onClick={() => onLoadDraft(dBody, dSpec)} className={secondaryBtn} title="편집기의 구조와 예외·주의를 이 초안으로 바꿉니다 (저장 전까지는 적용되지 않습니다)">편집기에 불러오기</button>
                </div>
              </div>
            )
          })()}
          {r.mode === 'analyze' && r.status === 'failed' && r.answer && <p className="text-xs text-content-secondary whitespace-pre-wrap">{r.answer.slice(0, 600)}</p>}

          {r.mode === 'verify' && r.result && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded-full text-[12px] font-semibold ${r.result.passed ? 'bg-green-500/15 text-green-600' : 'bg-red-500/15 text-red-500'}`}>{r.result.passed ? '통과' : '미통과'}</span>
                <span className="text-xs text-content-tertiary">단계 {r.result.steps}개 · 실패 {r.result.failed_steps}개 · 반복 차단 {r.result.loop_blocks}회 · {formatDuration(r.result.seconds * 1000)}</span>
              </div>
              <p className="text-[13px] text-content-primary">{r.result.summary}</p>
              {r.result.flow && r.result.flow.length > 0 && (
                <ul className="space-y-0.5 text-[12.5px]">
                  {r.result.flow.map((f) => (
                    <li key={f.key} className="flex gap-2 items-baseline">
                      <span className={`w-[64px] flex-shrink-0 font-medium ${FLOW_STATUS[f.status].cls}`}>{FLOW_STATUS[f.status].label}</span>
                      <span className="text-content-primary flex-shrink-0">{f.title}</span>
                      {f.note && <span className="text-content-tertiary truncate min-w-0" title={f.note}>{f.note}</span>}
                    </li>
                  ))}
                </ul>
              )}
              {r.result.issues.length > 0 && <ul className="list-disc pl-5 text-[12.5px] text-content-secondary space-y-0.5">{r.result.issues.map((x, i) => <li key={i}>{x}</li>)}</ul>}
              <p className="text-xs text-content-muted">통과 여부는 에이전트의 보고와 실행 기록으로 판정한 것입니다. 위 스크린샷으로 마지막 화면을 직접 확인하세요.</p>
              {(r.draft_body || r.draft_spec) && (
                <div className="flex gap-2 flex-wrap">
                  {r.result.passed && (
                    <button onClick={() => { if (confirm('이 내용을 검증됨으로 저장할까요?')) onSaveVerified(r.draft_body ?? '', siteSpecOf(r.draft_spec)) }} disabled={saving || !canSave} className={primaryBtn}>
                      {saving ? '저장 중…' : '검증됨으로 저장'}
                    </button>
                  )}
                  <button onClick={() => onLoadDraft(r.draft_body ?? '', siteSpecOf(r.draft_spec))} className={secondaryBtn}>편집기에 불러오기</button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {runs.data && runs.data.length > 1 && (
        <div className="space-y-0.5">
          <div className="text-xs text-content-tertiary">이 사이트의 최근 실행</div>
          {runs.data.map((x) => (
            <button
              key={x.id}
              onClick={() => setRunId(x.id)}
              className={`w-full flex items-center gap-2 px-2 py-1 rounded-[var(--radius-md)] border-none cursor-pointer text-left text-[12px] ${x.id === runId ? 'bg-surface-active' : 'bg-transparent hover:bg-surface-hover'}`}
            >
              <span className="text-content-primary w-[56px] flex-shrink-0">{x.mode === 'analyze' ? '분석' : '재현 검증'}</span>
              <span className={`px-1.5 rounded-full text-[10.5px] ${STATUS[x.status].cls}`}>{x.mode === 'verify' && x.result ? (x.result.passed ? '통과' : '미통과') : STATUS[x.status].label}</span>
              <span className="text-content-tertiary truncate flex-1">{x.scenario}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

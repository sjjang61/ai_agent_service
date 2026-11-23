import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { emptySiteSpec, siteProfilesApi, siteSpecOf, type SiteCategory, type SiteInput, type SiteProfile, type SiteVertical } from '../../api/siteProfiles'
import { errorText, inputCls, primaryBtn } from '../skills/common'
import { Field, TextArea, secondaryBtn } from './fields'
import StatusBadge from './StatusBadge'
import HistoryPanel from './HistoryPanel'
import CommandsField from './CommandsField'
import SkillRefsField from './SkillRefsField'
import AnalysisPanel from './AnalysisPanel'
import { SiteSpecEditor } from './SpecEditors'

interface Props {
  /** 없으면 새 사이트 */
  site: SiteProfile | null
  verticals: SiteVertical[]
  categories: SiteCategory[]
  defaultVertical?: string | null
  defaultCategory?: string | null
  onSaved: (id: string) => void
  onDeleted: () => void
}

const today = () => new Date().toISOString().slice(0, 10)

export default function SiteEditor({ site, verticals, categories, defaultVertical, defaultCategory, onSaved, onDeleted }: Props) {
  const qc = useQueryClient()
  const [form, setForm] = useState<SiteInput>(
    site
      ? { name: site.name, vertical: site.vertical, category: site.category, reference_skills: site.reference_skills, reference_commands: site.reference_commands, domains: site.domains, aliases: site.aliases, body: site.body, spec: siteSpecOf(site.spec), status: site.status, verified_at: site.verified_at, enabled: site.enabled }
      : { name: '', vertical: defaultVertical ?? null, category: defaultCategory ?? null, domains: '', aliases: '', body: '', spec: emptySiteSpec(), status: 'draft', verified_at: null, enabled: true },
  )
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [panel, setPanel] = useState<'history' | 'analysis' | null>(null)
  const [preview, setPreview] = useState('')
  const set = <K extends keyof SiteInput>(k: K, v: SiteInput[K]) => setForm((f) => ({ ...f, [k]: v }))
  const refresh = () => qc.invalidateQueries({ queryKey: ['site-profiles'] })
  const vspec = verticals.find((v) => v.key === form.vertical)?.spec

  const save = useMutation({
    mutationFn: async (data: SiteInput) =>
      site ? (await siteProfilesApi.updateSite(site.id, { ...data, version: site.version })).data : (await siteProfilesApi.createSite(data)).data,
    onSuccess: (s) => { setError(''); refresh(); onSaved(s.id) },
    onError: (e) => setError(errorText(e, '저장하지 못했습니다')),
  })
  const del = useMutation({
    mutationFn: () => siteProfilesApi.deleteSite(site!.id),
    onSuccess: () => { refresh(); onDeleted() },
    onError: (e) => setError(errorText(e, '삭제하지 못했습니다')),
  })

  // 미리보기: 지금 입력한 내용이 에이전트에게 어떻게 주어지는지 (입력이 멈추면 갱신)
  useEffect(() => {
    if (!showPreview) return
    const t = setTimeout(() => {
      siteProfilesApi.preview(form).then((r) => setPreview(r.data.text)).catch(() => setPreview('미리보기를 만들지 못했습니다'))
    }, 400)
    return () => clearTimeout(t)
  }, [showPreview, form])

  // 사용 안 함 전환: 저장된 값 그대로 사용 여부만 바꿔 바로 저장한다 (편집 중인 다른 내용은 건드리지 않는다)
  const toggleEnabled = () => {
    if (!site) return
    const next = !site.enabled
    if (!next && !confirm(`“${site.name}” 을(를) 사용 안 함으로 바꿀까요?\n에이전트가 이 사이트(${site.domains})에 접속하지 않고, 이 사이트의 요령도 전달하지 않습니다.`)) return
    save.mutate({ name: site.name, vertical: site.vertical, domains: site.domains, aliases: site.aliases, body: site.body, spec: siteSpecOf(site.spec), status: site.status, verified_at: site.verified_at, enabled: next })
  }
  const markVerified = () => { const next = { ...form, status: 'verified' as const, verified_at: today() }; setForm(next); save.mutate(next) }
  const copyMd = async () => {
    try { await navigator.clipboard.writeText(site!.md); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch { setError('복사하지 못했습니다') }
  }
  const canSave = !!form.name.trim() && !!form.domains.trim()

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h2 className="text-[17px] font-semibold text-content-primary">{site ? site.name : '새 사이트'}</h2>
        {site && <StatusBadge site={site} />}
        {site?.verified_at && <span className="text-xs text-content-tertiary">확인 {site.verified_at}</span>}
        {site && (
          <button
            onClick={toggleEnabled}
            disabled={save.isPending}
            title={site.enabled ? '에이전트가 이 사이트에 접속하지 않게 합니다 (봇 확인이 풀리지 않는 사이트 등)' : '다시 에이전트가 이 사이트를 쓸 수 있게 합니다'}
            className={`ml-auto ${secondaryBtn}`}
          >
            {site.enabled ? '사용 안 함으로 바꾸기' : '다시 사용하기'}
          </button>
        )}
      </div>
      {site && !site.enabled && (
        <div className="rounded-[var(--radius-md)] border border-border bg-surface-secondary px-3 py-2 text-[13px] text-content-secondary">
          이 사이트는 <b>사용 안 함</b> 상태입니다. 에이전트는 {site.domains} 에 접속하지 않고(시도하면 건너뜁니다), 이 사이트의 요령도 받지 않습니다. 사이트를 다시 분석하는 것은 가능합니다.
        </div>
      )}
      <div className="grid grid-cols-2 gap-3">
        <Field label="이름">
          <input value={form.name} onChange={(e) => set('name', e.target.value)} className={inputCls} placeholder="예: 네이버 항공권" />
        </Field>
        <Field label="분야">
          <select value={form.vertical ?? ''} onChange={(e) => set('vertical', e.target.value || null)} className={inputCls}>
            <option value="">(분야 없음)</option>
            {categories.map((c) => {
              const vs = verticals.filter((v) => v.category === c.key)
              return vs.length > 0 ? <optgroup key={c.key} label={c.name}>{vs.map((v) => <option key={v.key} value={v.key}>{v.name}</option>)}</optgroup> : null
            })}
            {verticals.filter((v) => !v.category || !categories.some((c) => c.key === v.category)).map((v) => <option key={v.key} value={v.key}>{v.name}</option>)}
          </select>
        </Field>
      </div>
      {!form.vertical && (
        <Field label="카테고리" hint="분야가 없는 사이트가 속할 상위 분류입니다. 분야를 고르면 그 분야의 카테고리를 따릅니다.">
          <select value={form.category ?? ''} onChange={(e) => set('category', e.target.value || '')} className={inputCls}>
            <option value="">(카테고리 없음)</option>
            {categories.map((c) => <option key={c.key} value={c.key}>{c.name}</option>)}
          </select>
        </Field>
      )}
      <Field label="도메인" hint="쉼표로 구분. 하위 도메인도 맞습니다. 주소를 붙여 넣어도 도메인만 남깁니다. 더 구체적인 도메인(flight.naver.com)이 넓은 도메인(naver.com)보다 먼저 적용됩니다. 한 사이트가 여러 분야를 가지면 '아고다 · 호텔'처럼 분야마다 따로 만드세요 (같은 도메인은 분야가 다를 때만 쓸 수 있습니다).">
        <input value={form.domains} onChange={(e) => set('domains', e.target.value)} className={inputCls} placeholder="flight.naver.com" />
      </Field>
      <SkillRefsField value={form.reference_skills ?? ''} onChange={(v) => set('reference_skills', v)} scope="사이트" />
      <CommandsField value={form.reference_commands ?? []} onChange={(v) => set('reference_commands', v)} />
      <Field label="별칭" hint="쉼표로 구분. 작업 문장에 이 단어가 나오면 시작할 때 요령이 붙습니다. '다음'처럼 흔한 단어는 피하세요.">
        <input value={form.aliases} onChange={(e) => set('aliases', e.target.value)} className={inputCls} placeholder="네이버항공권, 네이버 항공권" />
      </Field>
      <div className="space-y-1">
        <span className="text-[13px] font-medium text-content-primary">구조: 진입 주소·메뉴 지도·입력 방법·단계별 동작</span>
        <p className="text-xs text-content-tertiary">직접 확인한 것만 적으세요. 입력값과 단계는 분야({verticals.find((v) => v.key === form.vertical)?.name ?? '분야 없음'})가 정의한 것을 따릅니다.</p>
        <SiteSpecEditor value={form.spec} vertical={vspec} onChange={(spec) => set('spec', spec)} />
      </div>
      <Field label="예외·주의 (자유 서술)" hint="구조에 담기지 않는, 이 사이트에서만 맞는 함정을 에이전트에게 그대로 전달합니다: 로그인·캡차, 오류 화면, 화면이 바뀌는 조건.">
        <TextArea value={form.body} onChange={(v) => set('body', v)} rows={6} />
      </Field>
      <div className="grid grid-cols-3 gap-3">
        <Field label="상태" hint="초안은 에이전트에게 주지 않습니다.">
          <select value={form.status} onChange={(e) => set('status', e.target.value as SiteInput['status'])} className={inputCls}>
            <option value="verified">검증됨</option>
            <option value="draft">초안</option>
            <option value="stale">오래됨</option>
          </select>
        </Field>
        <Field label="확인일" hint="마지막으로 직접 확인한 날">
          <input type="date" value={form.verified_at ?? ''} onChange={(e) => set('verified_at', e.target.value || null)} className={inputCls} />
        </Field>
        <Field label="사용" hint="끄면 에이전트가 이 사이트에 접속하지 않습니다. 요령만 주지 않으려면 상태를 '초안'으로 두세요.">
          <label className="flex items-center gap-2 h-[42px] text-[13px] text-content-primary cursor-pointer">
            <input type="checkbox" checked={form.enabled} onChange={(e) => set('enabled', e.target.checked)} />
            사용 (끄면 접속하지 않음)
          </label>
        </Field>
      </div>

      <div>
        <button onClick={() => setShowPreview((v) => !v)} className="text-[13px] text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer p-0">
          {showPreview ? '▾' : '▸'} 에이전트에게 주어지는 모습
        </button>
        {showPreview && (
          <pre className="mt-2 p-3 bg-surface-secondary border border-border rounded-[var(--radius-md)] text-[12.5px] text-content-primary whitespace-pre-wrap break-words max-h-[320px] overflow-y-auto">
            {preview || '…'}
          </pre>
        )}
      </div>

      {error && <div className="text-[13px] text-red-500">{error}</div>}
      <div className="border-t border-border pt-3 space-y-2">
        <div className="flex gap-1">
          {([['analysis', '웹사이트 분석'], ['history', '수정 이력']] as const).map(([k, label]) => (
            <button
              key={k}
              onClick={() => setPanel(panel === k ? null : k)}
              disabled={k === 'history' && !site}
              className={`px-3 py-1.5 rounded-full text-[13px] border-none cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${panel === k ? 'bg-surface-active text-content-primary' : 'bg-transparent text-content-secondary hover:bg-surface-hover'}`}
            >
              {label}
            </button>
          ))}
        </div>
        {panel === 'analysis' && (
          <AnalysisPanel
            name={form.name}
            vertical={form.vertical}
            domains={form.domains}
            currentBody={form.body}
            currentSpec={form.spec}
            verticalSpec={vspec}
            onLoadDraft={(body, spec) => setForm((f) => ({ ...f, body, spec }))}
            onSaveVerified={(body, spec) => { const next = { ...form, body, spec, status: 'verified' as const, verified_at: today(), enabled: true }; setForm(next); save.mutate(next) }}
            saving={save.isPending}
            canSave={canSave}
          />
        )}
        {panel === 'history' && site && (
          <HistoryPanel
            queryKey={['site-revisions', site.id]}
            load={() => siteProfilesApi.siteRevisions(site.id)}
            current={{ name: site.name, vertical: site.vertical, category: site.category, reference_skills: site.reference_skills, reference_commands: site.reference_commands, domains: site.domains, aliases: site.aliases, body: site.body, spec: site.spec, status: site.status, verified_at: site.verified_at, enabled: site.enabled }}
            labels={{ name: '이름', vertical: '분야', category: '카테고리', reference_skills: '참고 스킬', reference_commands: '사전 실행 명령', domains: '도메인', aliases: '별칭', body: '예외·주의', spec: '구조', status: '상태', verified_at: '확인일', enabled: '사용' }}
            restore={(revId) => siteProfilesApi.restoreSite(site.id, revId)}
            onRestored={() => { qc.invalidateQueries({ queryKey: ['site-profiles'] }); qc.invalidateQueries({ queryKey: ['site-revisions', site.id] }) }}
          />
        )}
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={() => save.mutate(form)} disabled={save.isPending || !canSave} className={primaryBtn}>
          {save.isPending ? '저장 중…' : '저장'}
        </button>
        {site && <button onClick={markVerified} disabled={save.isPending || !canSave} className={secondaryBtn} title="상태를 검증됨으로, 확인일을 오늘로 바꿔 저장합니다">확인함으로 저장</button>}
        {site && <button onClick={copyMd} className={secondaryBtn}>{copied ? '복사됨' : 'md 복사'}</button>}
        {site && (
          <button
            onClick={() => { if (confirm(`사이트 “${site.name}” 을(를) 삭제할까요?`)) del.mutate() }}
            className="ml-auto text-[13px] text-content-muted hover:text-accent-red border-none bg-transparent cursor-pointer"
          >
            삭제
          </button>
        )}
      </div>
    </div>
  )
}

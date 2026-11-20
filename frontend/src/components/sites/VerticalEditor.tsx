import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { emptyVerticalSpec, siteProfilesApi, verticalSpecOf, type SiteVertical, type VerticalInput } from '../../api/siteProfiles'
import { errorText, inputCls, primaryBtn } from '../skills/common'
import { Field, TextArea, secondaryBtn } from './fields'
import HistoryPanel from './HistoryPanel'
import { VerticalSpecEditor } from './SpecEditors'

interface Props {
  /** 없으면 새 분야 */
  vertical: SiteVertical | null
  onSaved: (key: string) => void
  onDeleted: () => void
}

const EMPTY: VerticalInput = { key: '', name: '', keywords: '', stop_words: '', stop_urls: '', body: '', checklist: '', spec: emptyVerticalSpec() }

export default function VerticalEditor({ vertical, onSaved, onDeleted }: Props) {
  const qc = useQueryClient()
  const [form, setForm] = useState<VerticalInput>(vertical ? { ...vertical, spec: verticalSpecOf(vertical.spec) } : EMPTY)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const set = (k: Exclude<keyof VerticalInput, 'spec' | 'version'>) => (v: string) => setForm((f) => ({ ...f, [k]: v }))
  const refresh = () => qc.invalidateQueries({ queryKey: ['site-profiles'] })

  const save = useMutation({
    mutationFn: async () =>
      vertical
        ? (await siteProfilesApi.updateVertical(vertical.key, { ...form, version: vertical.version })).data
        : (await siteProfilesApi.createVertical(form)).data,
    onSuccess: (v) => { setError(''); refresh(); onSaved(v.key) },
    onError: (e) => setError(errorText(e, '저장하지 못했습니다')),
  })
  const del = useMutation({
    mutationFn: () => siteProfilesApi.deleteVertical(vertical!.key),
    onSuccess: () => { refresh(); onDeleted() },
    onError: (e) => setError(errorText(e, '삭제하지 못했습니다')),
  })

  const copyMd = async () => {
    try { await navigator.clipboard.writeText(vertical!.md); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch { setError('복사하지 못했습니다') }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-[17px] font-semibold text-content-primary">{vertical ? `분야 · ${vertical.name}` : '새 분야'}</h2>
        <p className="text-[13px] text-content-secondary mt-0.5">
          분야에 속한 모든 사이트가 함께 쓰는 지침입니다. 에이전트는 이 분야의 사이트를 만나면 이 지침을 사이트 요령보다 먼저 받습니다.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="이름">
          <input value={form.name} onChange={(e) => set('name')(e.target.value)} className={inputCls} placeholder="예: 항공권" />
        </Field>
        <Field label="키" hint={vertical ? '만든 뒤에는 바꿀 수 없습니다 (사이트가 이 키로 분야를 가리킵니다)' : '영문 소문자·숫자·밑줄. 예: car_rental'}>
          <input value={form.key ?? ''} onChange={(e) => set('key')(e.target.value)} disabled={!!vertical} className={`${inputCls} disabled:opacity-60`} />
        </Field>
      </div>
      <Field label="키워드" hint="쉼표로 구분. 작업 문장에 나오면 사이트를 말하지 않아도 이 분야 지침이 붙습니다. '영화'처럼 흔한 단어는 피하세요.">
        <input value={form.keywords} onChange={(e) => set('keywords')(e.target.value)} className={inputCls} placeholder="항공권, 항공편" />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="누르지 않을 버튼 문구" hint="쉼표로 구분. 짧은 버튼 라벨에 이 문구가 있으면 누르지 않습니다. 결제하기 같은 공통 문구는 이미 막혀 있습니다.">
          <input value={form.stop_words} onChange={(e) => set('stop_words')(e.target.value)} className={inputCls} placeholder="예약 확정" />
        </Field>
        <Field label="이동하지 않을 주소 문구" hint="쉼표로 구분. 주소에 이 문구가 있으면 이동하지 않습니다.">
          <input value={form.stop_urls} onChange={(e) => set('stop_urls')(e.target.value)} className={inputCls} />
        </Field>
      </div>
      <div className="space-y-1">
        <span className="text-[13px] font-medium text-content-primary">구조: 입력값과 표준 진행 단계</span>
        <VerticalSpecEditor value={form.spec} onChange={(spec) => setForm((f) => ({ ...f, spec }))} />
      </div>
      <Field label="공통 지침 (자유 서술)" hint="구조에 담기지 않는 지침을 에이전트에게 그대로 전달합니다: 주의할 점, 보고 항목, 멈출 지점.">
        <TextArea value={form.body} onChange={set('body')} rows={14} />
      </Field>
      <Field label="분석 체크리스트" hint="새 사이트를 분석할 때 확인할 질문입니다. 에이전트에게는 전달되지 않습니다.">
        <TextArea value={form.checklist} onChange={set('checklist')} rows={8} />
      </Field>
      {error && <div className="text-[13px] text-red-500">{error}</div>}
      {vertical && (
        <div className="border-t border-border pt-3 space-y-2">
          <button
            onClick={() => setShowHistory((v) => !v)}
            className={`px-3 py-1.5 rounded-full text-[13px] border-none cursor-pointer ${showHistory ? 'bg-surface-active text-content-primary' : 'bg-transparent text-content-secondary hover:bg-surface-hover'}`}
          >
            수정 이력
          </button>
          {showHistory && (
            <HistoryPanel
              queryKey={['vertical-revisions', vertical.key]}
              load={() => siteProfilesApi.verticalRevisions(vertical.key)}
              current={{ name: vertical.name, keywords: vertical.keywords, stop_words: vertical.stop_words, stop_urls: vertical.stop_urls, body: vertical.body, checklist: vertical.checklist, spec: vertical.spec }}
              labels={{ name: '이름', keywords: '키워드', stop_words: '누르지 않을 버튼 문구', stop_urls: '이동하지 않을 주소 문구', body: '공통 지침', checklist: '분석 체크리스트', spec: '구조 (입력값·표준 단계)' }}
              restore={(revId) => siteProfilesApi.restoreVertical(vertical.key, revId)}
              onRestored={() => { refresh(); qc.invalidateQueries({ queryKey: ['vertical-revisions', vertical.key] }) }}
            />
          )}
        </div>
      )}

      <div className="flex items-center gap-2">
        <button onClick={() => save.mutate()} disabled={save.isPending || !form.name.trim() || !form.body.trim() || (!vertical && !form.key?.trim())} className={primaryBtn}>
          {save.isPending ? '저장 중…' : '저장'}
        </button>
        {vertical && <button onClick={copyMd} className={secondaryBtn}>{copied ? '복사됨' : 'md 복사'}</button>}
        {vertical && (
          <button
            onClick={() => { if (confirm(`분야 “${vertical.name}” 을(를) 삭제할까요?`)) del.mutate() }}
            disabled={vertical.site_count > 0}
            title={vertical.site_count > 0 ? '이 분야를 쓰는 사이트가 있어 삭제할 수 없습니다' : ''}
            className="ml-auto text-[13px] text-content-muted hover:text-accent-red border-none bg-transparent cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            삭제
          </button>
        )}
      </div>
    </div>
  )
}

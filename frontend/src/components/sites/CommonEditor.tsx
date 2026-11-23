import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { siteProfilesApi } from '../../api/siteProfiles'
import { errorText, primaryBtn } from '../skills/common'
import { Field, TextArea } from './fields'

/** 분야·사이트와 무관하게 모든 브라우저 작업과 사이트 분석에 붙는 전체 공통 지침 */
export default function CommonEditor() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['site-common'], queryFn: async () => (await siteProfilesApi.getCommon()).data })
  if (isLoading || !data) return <p className="text-[13px] text-content-secondary">불러오는 중…</p>
  return <Form key={data.version} initial={data.body} version={data.version} updatedBy={data.updated_by} onSaved={() => qc.invalidateQueries({ queryKey: ['site-common'] })} />
}

function Form({ initial, version, updatedBy, onSaved }: { initial: string; version: number; updatedBy: string | null; onSaved: () => void }) {
  const [body, setBody] = useState(initial)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const save = useMutation({
    mutationFn: async () => (await siteProfilesApi.updateCommon({ body, version })).data,
    onSuccess: () => { setError(''); setSaved(true); setTimeout(() => setSaved(false), 1500); onSaved() },
    onError: (e) => setError(errorText(e, '저장하지 못했습니다')),
  })
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-[17px] font-semibold text-content-primary">전체 공통 지침</h2>
        <p className="text-[13px] text-content-secondary mt-0.5">
          분야·사이트와 상관없이 모든 브라우저 작업의 시작 지침과 사이트 분석(초안 만들기·재현 검증)에 맨 앞으로 붙는 지침입니다. 예: “웹사이트 분석 시 모든 팝업은 항상 닫는다”.
        </p>
      </div>
      <Field label="지침 (markdown)" hint={`${body.length}/4000자. 비워 두면 공통 지침 없이 동작합니다.${updatedBy ? ` 마지막 수정: ${updatedBy}` : ''}`}>
        <TextArea value={body} onChange={setBody} rows={14} />
      </Field>
      {error && <p className="text-[13px] text-red-500">{error}</p>}
      <div className="flex items-center gap-3">
        <button onClick={() => save.mutate()} disabled={save.isPending || body === initial} className={`${primaryBtn} disabled:opacity-50`}>{save.isPending ? '저장 중…' : '저장'}</button>
        {saved && <span className="text-[13px] text-content-secondary">저장했습니다</span>}
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { memoryApi } from '../../api/memory'
import { T } from '../skills/typography'
import { errorText, inputCls, primaryBtn } from '../skills/common'
import { formatFullDateTime } from '../../utils/time'

const PLACEHOLDER = `## 배경
- 백엔드 개발자, Python·FastAPI 사용

## 성향·선호
- 코드 예제를 먼저 보고 싶어 한다

## 작업 방식
- 답변은 존댓말 한국어로 한다`

/** USER.md: 사용자의 성향·배경을 한 문서로 영구 보관한다. 사실·작업 방식 메모리를 'AI로 합치기'로 정리할 수 있다. */
export default function ProfileEditor() {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['memory-profile'], queryFn: async () => (await memoryApi.getProfile()).data })
  const [text, setText] = useState('')
  const [fromMerge, setFromMerge] = useState(false) // 합치기 결과를 그대로 저장하면 '합침'으로 표시한다
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { if (data) { setText(data.content); setFromMerge(false) } }, [data])

  const refresh = () => qc.invalidateQueries({ queryKey: ['memory-profile'] })
  const save = useMutation({
    mutationFn: () => memoryApi.saveProfile(text, fromMerge),
    onSuccess: () => { setError(''); setMsg('저장했습니다'); refresh() },
    onError: (e) => setError(errorText(e, '저장하지 못했습니다')),
  })
  const merge = useMutation({
    mutationFn: async () => (await memoryApi.mergeProfile()).data.content,
    onSuccess: (c) => { setError(''); setText(c); setFromMerge(true); setMsg('합친 결과입니다. 확인하고 저장하세요') },
    onError: (e) => setError(errorText(e, '합치지 못했습니다')),
  })
  const dirty = data ? text !== data.content || fromMerge : false

  return (
    <div className="space-y-3 max-w-[760px]">
      <p className={T.itemDesc}>
        사용자의 배경·성향·일하는 방식을 정리한 문서(USER.md)입니다. 에이전트가 모든 대화에서 이 문서를 먼저 읽고 반영합니다.
        직접 쓰거나, 저장된 사실·작업 방식 메모리를 AI가 한 문서로 합치게 할 수 있습니다 (비슷한 내용은 하나로 합쳐집니다).
      </p>
      <textarea
        value={text}
        onChange={(e) => { setText(e.target.value); setMsg('') }}
        rows={16}
        maxLength={4000}
        placeholder={PLACEHOLDER}
        className={`${inputCls} font-mono text-[13px] leading-relaxed resize-y`}
      />
      <div className="flex flex-wrap items-center gap-2">
        <button onClick={() => save.mutate()} disabled={!dirty || save.isPending} className={primaryBtn}>{save.isPending ? '저장 중...' : '저장'}</button>
        <button
          onClick={() => { if (!dirty || confirm('편집 중인 내용이 합친 결과로 바뀝니다. 계속할까요?')) merge.mutate() }}
          disabled={merge.isPending}
          className="flex items-center gap-1.5 px-3 py-2 rounded-md bg-surface-secondary hover:bg-surface-hover text-content-primary border border-border text-[13px] cursor-pointer disabled:opacity-50"
        >
          <Sparkles size={14} />{merge.isPending ? '합치는 중...' : 'AI로 합치기'}
        </button>
        <span className="text-xs text-content-tertiary">{text.length}/4000자</span>
        {msg && <span className="text-xs text-accent-green">{msg}</span>}
        {error && <span className="text-xs text-red-500">{error}</span>}
      </div>
      {data && (
        <p className="text-xs text-content-tertiary">
          {data.merged_at ? `마지막으로 합친 시각 ${formatFullDateTime(data.merged_at)}` : '아직 메모리를 합친 적이 없습니다'}
          {data.unmerged > 0 && ` · 합친 뒤 새로 저장·수정된 메모리 ${data.unmerged}개 (프롬프트에는 따로 전달됩니다)`}
        </p>
      )}
    </div>
  )
}

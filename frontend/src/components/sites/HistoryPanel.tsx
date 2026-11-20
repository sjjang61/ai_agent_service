import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import type { AxiosResponse } from 'axios'
import type { Revision } from '../../api/siteProfiles'
import { errorText } from '../skills/common'
import { formatFullDateTime } from '../../utils/time'
import DiffView from './DiffView'
import { secondaryBtn } from './fields'

const SOURCE_LABEL: Record<string, string> = { seed: '기본값', ui: '직접 수정', analysis: '분석', restore: '되돌림' }

interface Props {
  /** 이력 조회 쿼리 키·함수 */
  queryKey: unknown[]
  load: () => Promise<AxiosResponse<Revision[]>>
  /** 지금 저장된 내용 (비교 기준) */
  current: Record<string, unknown>
  /** 필드 이름 → 화면에 보일 이름 (본문 필드는 'body') */
  labels: Record<string, string>
  restore: (revId: string) => Promise<unknown>
  onRestored: () => void
}

const isEmpty = (v: unknown) => v === null || v === undefined || v === '' || (typeof v === 'object' && Object.keys(v as object).length === 0)
const show = (v: unknown) => (isEmpty(v) ? '(비어 있음)' : typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v))

/** 수정 이력: 버전 목록, 선택한 버전과 지금 내용의 차이, 그 버전으로 되돌리기. */
export default function HistoryPanel({ queryKey, load, current, labels, restore, onRestored }: Props) {
  const { data: revs = [], isLoading } = useQuery({ queryKey, queryFn: async () => (await load()).data })
  const [picked, setPicked] = useState<string | null>(null)
  const [error, setError] = useState('')
  const rev = revs.find((r) => r.id === picked) ?? null
  const doRestore = useMutation({
    mutationFn: (id: string) => restore(id),
    onSuccess: () => { setError(''); onRestored() },
    onError: (e) => setError(errorText(e, '되돌리지 못했습니다')),
  })

  if (isLoading) return <p className="text-xs text-content-tertiary">불러오는 중…</p>
  if (revs.length === 0) return <p className="text-xs text-content-tertiary">아직 수정 이력이 없습니다. 처음 저장하면 그 이전 상태부터 남습니다.</p>

  const changed = rev ? Object.keys(labels).filter((k) => show(rev.snapshot[k]) !== show(current[k])) : []
  return (
    <div className="grid grid-cols-[200px_1fr] gap-3">
      <ul className="max-h-[360px] overflow-y-auto space-y-0.5">
        {revs.map((r, i) => (
          <li key={r.id}>
            <button
              onClick={() => setPicked(r.id)}
              className={`w-full text-left px-2.5 py-1.5 rounded-[var(--radius-md)] border-none cursor-pointer text-[12px] ${picked === r.id ? 'bg-surface-active' : 'bg-transparent hover:bg-surface-hover'}`}
            >
              <div className="text-content-primary font-medium">v{r.version}{i === 0 && <span className="ml-1 text-content-tertiary font-normal">현재</span>}</div>
              <div className={picked === r.id ? 'text-content-secondary' : 'text-content-tertiary'}>{SOURCE_LABEL[r.source] ?? r.source}{r.author ? ` · ${r.author}` : ''}</div>
              <div className={picked === r.id ? 'text-content-secondary' : 'text-content-muted'}>{formatFullDateTime(r.created_at)}</div>
            </button>
          </li>
        ))}
      </ul>
      <div className="min-w-0 space-y-2">
        {!rev && <p className="text-xs text-content-tertiary">왼쪽에서 버전을 고르면 지금 내용과의 차이를 보여 줍니다.</p>}
        {rev && (
          <>
            {error && <div className="text-[13px] text-red-500">{error}</div>}
            {changed.length === 0 ? (
              <p className="text-xs text-content-tertiary">지금 내용과 같습니다.</p>
            ) : (
              changed.map((k) => (
                <div key={k} className="space-y-1">
                  <div className="text-xs font-medium text-content-primary">{labels[k]}</div>
                  {k === 'body' || k === 'checklist' || k === 'spec' ? (
                    <DiffView before={show(current[k])} after={show(rev.snapshot[k])} />
                  ) : (
                    <div className="text-[12px] text-content-secondary">
                      <span className="text-red-500">{show(current[k])}</span> → <span className="text-green-600">{show(rev.snapshot[k])}</span>
                    </div>
                  )}
                </div>
              ))
            )}
            <p className="text-xs text-content-muted">빨강은 지금 내용에만 있는 것, 초록은 이 버전에만 있는 것입니다.</p>
            {changed.length > 0 && (
              <button
                onClick={() => { if (confirm(`v${rev.version} 으로 되돌릴까요? 지금 내용은 이력에 남습니다.`)) doRestore.mutate(rev.id) }}
                disabled={doRestore.isPending}
                className={secondaryBtn}
              >
                {doRestore.isPending ? '되돌리는 중…' : `v${rev.version} 으로 되돌리기`}
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}

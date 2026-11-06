import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, Loader2, RefreshCw, RotateCcw } from 'lucide-react'
import { adminApi } from '../../api/admin'
import { errorText } from '../skills/common'
import { T } from '../skills/typography'
import { formatFullDateTime } from '../../utils/time'
import type { PricingRefreshResult, PricingState } from '../../types/admin'

const METHOD_LABEL: Record<string, string> = {
  structured: '페이지의 구조화된 가격 데이터',
  table: 'HTML 가격표',
  llm: 'AI 추출 (형식이 달라 AI 가 읽음 — 값을 확인하세요)',
}
const SOURCE_BADGE: Record<string, { text: string; cls: string }> = {
  default: { text: '기본', cls: 'bg-surface-tertiary text-content-muted' },
  page: { text: '페이지 갱신', cls: 'bg-accent-green/15 text-accent-green' },
  custom: { text: '설정', cls: 'bg-accent-amber/15 text-accent-amber' },
}
const usd = (v: number | null) => (v == null ? '-' : `$${v}`)

/** 가격 정책: 예상 비용 계산에 쓰는 모델 단가의 출처 URL 을 정하고, 그 페이지에서 단가를 갱신한다. */
export default function PricingPanel({ onUpdated }: { onUpdated: () => void }) {
  const qc = useQueryClient()
  const { data } = useQuery<PricingState>({
    queryKey: ['pricing'],
    queryFn: async () => (await adminApi.getPricing()).data,
  })
  const [url, setUrl] = useState<string | null>(null) // 편집 중인 값 (null 이면 저장된 값을 보여 준다)
  const [error, setError] = useState('')
  const [result, setResult] = useState<PricingRefreshResult | null>(null)
  const [showTable, setShowTable] = useState(false)
  const [filter, setFilter] = useState('')

  const current = url ?? data?.url ?? ''
  const dirty = !!data && current.trim() !== data.url

  const save = useMutation({
    mutationFn: (u: string) => adminApi.setPricingUrl(u.trim()),
    onSuccess: (r) => { qc.setQueryData(['pricing'], r.data); setUrl(null); setError('') },
    onError: (e) => setError(errorText(e, 'URL 을 저장하지 못했습니다')),
  })
  const refresh = useMutation({
    mutationFn: async () => {
      if (dirty) await adminApi.setPricingUrl(current.trim()) // 바꾼 URL 을 먼저 저장한 뒤 갱신한다
      return (await adminApi.refreshPricing()).data
    },
    onSuccess: (r) => { setResult(r); setUrl(null); setError(''); qc.invalidateQueries({ queryKey: ['pricing'] }); onUpdated() },
    onError: (e) => { setResult(null); setError(errorText(e, '가격을 갱신하지 못했습니다')); qc.invalidateQueries({ queryKey: ['pricing'] }) },
  })

  const rows = (data?.prices ?? []).filter((p) => !filter.trim() || p.model.includes(filter.trim().toLowerCase()))

  return (
    <div className="bg-surface-secondary rounded-lg p-4 border border-border mt-8">
      <h2 className={`${T.section} mb-1`}>가격 정책</h2>
      <p className="text-xs text-content-muted mb-4">
        예상 비용은 모델 단가 × 토큰으로 계산합니다. 단가를 가져올 가격 페이지 주소(https)를 정하고 "가격 업데이트"를 누르면 그 페이지의 Standard 요금으로 단가표를 갱신합니다.
      </p>

      <div className="flex gap-2 flex-wrap items-center">
        <input
          value={current}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://developers.openai.com/api/docs/pricing"
          className="flex-1 min-w-[280px] px-3 py-2 bg-surface-primary border border-border rounded-lg text-sm text-content-primary focus:outline-none focus:border-accent-primary"
        />
        <button
          onClick={() => save.mutate(current)}
          disabled={!dirty || save.isPending || refresh.isPending}
          className="px-3 py-2 rounded-lg border border-border bg-transparent text-sm text-content-secondary hover:text-content-primary disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
        >
          {save.isPending ? '저장 중...' : 'URL 저장'}
        </button>
        <button
          onClick={() => data && setUrl(data.default_url)}
          disabled={!data || current === data.default_url}
          title="기본 URL(OpenAI 가격 페이지)로 되돌립니다. 저장해야 적용됩니다."
          className="px-2.5 py-2 rounded-lg border border-border bg-transparent text-content-secondary hover:text-content-primary disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
        >
          <RotateCcw size={14} />
        </button>
        <button
          onClick={() => refresh.mutate()}
          disabled={refresh.isPending || !current.trim()}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-accent-primary hover:bg-accent-primary/90 text-white text-sm font-medium border-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {refresh.isPending ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          가격 업데이트
        </button>
      </div>

      {error && <p className="mt-3 text-[13px] text-accent-red">{error}</p>}
      {result && (
        <div className="mt-3 text-[13px] rounded-lg border border-accent-green/30 bg-accent-green/10 text-accent-green px-3 py-2">
          {result.model_count}개 모델의 단가를 갱신했습니다 ({METHOD_LABEL[result.method] ?? result.method}).
          {result.added.length > 0 && <div className="text-content-secondary mt-1">새로 추가: {result.added.join(', ')}</div>}
          {result.changed.length > 0 && (
            <ul className="text-content-secondary mt-1 list-disc pl-5">
              {result.changed.map((c) => (
                <li key={c.model}>{c.model}: 입력 {usd(c.old.input)} → {usd(c.new.input)}, 출력 {usd(c.old.output)} → {usd(c.new.output)}</li>
              ))}
            </ul>
          )}
          {result.added.length === 0 && result.changed.length === 0 && <div className="text-content-secondary mt-1">바뀐 가격이 없습니다.</div>}
        </div>
      )}

      {data && (
        <p className="mt-3 text-xs text-content-muted">
          마지막 갱신: {data.last_updated_at ? formatFullDateTime(data.last_updated_at) : '아직 없음 (코드의 기본 단가표 사용 중)'}
          {data.last_method && ` · ${METHOD_LABEL[data.last_method] ?? data.last_method} · ${data.last_count}개 모델`}
          {data.last_status && data.last_status !== '성공' && <span className="text-accent-red"> · {data.last_status}</span>}
        </p>
      )}

      <button
        onClick={() => setShowTable((s) => !s)}
        className="mt-4 flex items-center gap-1 text-[13px] text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer p-0"
      >
        {showTable ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        적용 중인 단가표 ({data?.prices.length ?? 0}개 모델, USD / 1M 토큰)
      </button>
      {showTable && (
        <div className="mt-2">
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="모델 검색"
            className="mb-2 px-3 py-1.5 bg-surface-primary border border-border rounded-lg text-xs text-content-primary focus:outline-none focus:border-accent-primary"
          />
          <div className="overflow-x-auto max-h-[360px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface-secondary">
                <tr className="text-content-muted border-b border-border">
                  <th className="text-left py-2 px-2">모델</th>
                  <th className="text-right py-2 px-2">입력</th>
                  <th className="text-right py-2 px-2">캐시 입력</th>
                  <th className="text-right py-2 px-2">출력</th>
                  <th className="text-left py-2 px-2">출처</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <tr key={p.model} className="border-b border-border/50">
                    <td className="py-1.5 px-2 text-content-primary">{p.model}</td>
                    <td className="py-1.5 px-2 text-right text-content-secondary">{usd(p.input)}</td>
                    <td className="py-1.5 px-2 text-right text-content-muted">{usd(p.cached_input)}</td>
                    <td className="py-1.5 px-2 text-right text-content-secondary">{usd(p.output)}</td>
                    <td className="py-1.5 px-2"><span className={`text-[10px] px-1.5 py-0.5 rounded ${SOURCE_BADGE[p.source].cls}`}>{SOURCE_BADGE[p.source].text}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Clock, GitMerge, Layers, Loader2, MessageSquare, RefreshCw, Trash2, X } from 'lucide-react'
import { memoryApi } from '../../api/memory'
import { errorText } from '../skills/common'
import type { ShortGroup, ShortMergePreview, ShortTermItem } from '../../types/memory'

/** 남은 시간을 '6일 23시간' / '3시간 12분' / '10분' 으로 */
function remaining(sec: number | null): string {
  if (sec == null) return '기간 정보 없음'
  const d = Math.floor(sec / 86400)
  const h = Math.floor((sec % 86400) / 3600)
  const m = Math.floor((sec % 3600) / 60)
  if (d > 0) return `${d}일 ${h}시간`
  if (h > 0) return `${h}시간 ${m}분`
  return `${Math.max(1, m)}분`
}

const refKey = (conversation_id: string, key: string) => `${conversation_id}\u0000${key}`

function ItemCard({ it, onDelete, showConv }: { it: ShortTermItem; onDelete: () => void; showConv?: boolean }) {
  return (
    <div className="rounded-xl p-4 bg-surface-secondary border border-border">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-[14px] font-medium text-content-primary">{it.key}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded border bg-accent-amber/15 text-accent-amber border-accent-amber/30">단기</span>
            <span className="inline-flex items-center gap-1 text-[11px] text-content-tertiary" title="이 시간이 지나면 자동으로 사라집니다 (갱신되면 다시 시작)">
              <Clock size={11} />
              남은 {remaining(it.expires_in_seconds)}
            </span>
          </div>
          <p className="text-[13px] text-content-secondary whitespace-pre-wrap break-words">{it.value}</p>
          {showConv && (
            <Link to={`/chat/${it.conversation_id}`} className="inline-flex items-center gap-1 mt-1.5 text-[11px] text-content-muted hover:text-content-primary no-underline" title="이 대화방으로 이동">
              <MessageSquare size={11} />
              <span className="truncate max-w-[300px]">{it.conversation_title || '(제목 없음)'}</span>
            </Link>
          )}
        </div>
        <button onClick={onDelete} className="p-1.5 text-content-muted hover:text-accent-red transition-colors flex-shrink-0" title="삭제">
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  )
}

/** 병합 미리보기: 합친 결과를 확인하고 적용한다. 합친 항목은 가장 최근에 쓴 대화방에 저장되고 원본은 지워진다. */
function MergeDialog({ preview, onApply, onClose, busy, error }: {
  preview: ShortMergePreview
  onApply: (merged: ShortMergePreview['merged']) => void
  onClose: () => void
  busy: boolean
  error: string
}) {
  const [merged, setMerged] = useState(preview.merged)
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onMouseDown={onClose}>
      <div className="w-full max-w-[640px] max-h-[88vh] flex flex-col bg-surface-primary border border-border rounded-[var(--radius-xl)] shadow-xl overflow-hidden" onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-label="단기 메모리 병합">
        <div className="flex items-center gap-2 px-6 pt-5 pb-3">
          <GitMerge size={18} className="text-accent-primary" />
          <h2 className="text-[16px] font-semibold text-content-primary">단기 메모리 병합 미리보기</h2>
          <div className="flex-1" />
          <button onClick={onClose} aria-label="닫기" className="text-content-tertiary hover:text-content-primary border-none bg-transparent cursor-pointer"><X size={18} /></button>
        </div>
        <p className="px-6 pb-3 text-xs text-content-secondary">
          {preview.conversation_count}개 대화의 {preview.source_count}개 항목을 아래 {merged.length}개로 합칩니다. 합친 항목은 가장 최근에 쓴
          <b> '{preview.target_conversation_title || '(제목 없음)'}'</b> 대화에 저장되고, 합쳐진 원본 항목은 모두 삭제됩니다. 필요 없는 항목은 ✕ 로 뺄 수 있습니다.
        </p>
        <div className="flex-1 overflow-y-auto px-6 pb-3 space-y-2">
          {merged.map((m, i) => (
            <div key={m.key} className="rounded-lg border border-border bg-surface-secondary p-3">
              <div className="flex items-start gap-2">
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-medium text-content-primary mb-0.5">{m.key}</div>
                  <textarea
                    value={m.value}
                    onChange={(e) => setMerged((l) => l.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)))}
                    rows={2}
                    maxLength={500}
                    className="w-full px-2 py-1.5 bg-surface-primary border border-border rounded-md text-[13px] text-content-secondary focus:outline-none focus:border-accent-primary resize-y"
                  />
                </div>
                <button onClick={() => setMerged((l) => l.filter((_, j) => j !== i))} title="이 항목 빼기" className="p-1 text-content-muted hover:text-accent-red border-none bg-transparent cursor-pointer"><X size={14} /></button>
              </div>
            </div>
          ))}
          {merged.length === 0 && <p className="text-xs text-content-muted py-4 text-center">남은 항목이 없습니다. 닫고 다시 시도하세요.</p>}
        </div>
        {error && <p className="px-6 pb-2 text-xs text-accent-red">{error}</p>}
        <div className="flex justify-end gap-2 px-6 py-3 border-t border-border">
          <button onClick={onClose} className="px-4 py-2 rounded-lg border border-border bg-transparent text-sm text-content-secondary hover:text-content-primary cursor-pointer">취소</button>
          <button
            onClick={() => onApply(merged.filter((m) => m.value.trim()))}
            disabled={busy || merged.filter((m) => m.value.trim()).length === 0}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-accent-primary hover:bg-accent-primary/90 text-white text-sm font-medium border-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {busy && <Loader2 size={14} className="animate-spin" />}
            병합하기
          </button>
        </div>
      </div>
    </div>
  )
}

/**
 * 단기 메모리: 한 대화방에서만 쓰이는 임시 메모리. 저장하거나 갱신한 뒤 일정 시간(기본 7일)이 지나면 자동으로 사라진다.
 * '대화방별'은 대화방으로 묶어, '유사 내용별'은 AI 가 같은 주제끼리 묶어 보여 주며 그룹을 하나로 병합할 수 있다.
 */
export default function ShortTermMemoryList() {
  const qc = useQueryClient()
  const [mode, setMode] = useState<'conv' | 'topic'>('conv')
  const [preview, setPreview] = useState<{ group: ShortGroup; data: ShortMergePreview } | null>(null)
  const [mergeError, setMergeError] = useState('')

  const { data = [], isLoading, isError } = useQuery<ShortTermItem[]>({
    queryKey: ['short-term-memories'],
    queryFn: async () => (await memoryApi.listShortTermAll()).data,
    refetchInterval: 60_000, // 남은 시간이 줄어드는 것을 반영한다
  })
  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ['short-term-memories'] })
    qc.invalidateQueries({ queryKey: ['short-term-groups'] })
  }
  const del = useMutation({
    mutationFn: ({ conversation_id, key }: { conversation_id: string; key: string }) => memoryApi.deleteShortTerm(conversation_id, key),
    onSuccess: invalidateAll,
  })

  const groupsQuery = useQuery({
    queryKey: ['short-term-groups'],
    queryFn: async () => (await memoryApi.groupShortTerm()).data.groups,
    enabled: mode === 'topic' && data.length > 0,
    staleTime: 5 * 60_000,
    retry: false,
  })

  const previewMut = useMutation({
    mutationFn: async (group: ShortGroup) => ({ group, data: (await memoryApi.previewShortMerge(group.items)).data }),
    onSuccess: (r) => { setMergeError(''); setPreview(r) },
    onError: (e) => alert(errorText(e, '병합 미리보기를 만들지 못했습니다')),
  })
  const applyMut = useMutation({
    mutationFn: (merged: ShortMergePreview['merged']) => memoryApi.applyShortMerge(preview!.group.items, merged, preview!.data.target_conversation_id),
    onSuccess: () => { setPreview(null); invalidateAll() },
    onError: (e) => setMergeError(errorText(e, '병합하지 못했습니다')),
  })

  const byRef = useMemo(() => new Map(data.map((it) => [refKey(it.conversation_id, it.key), it])), [data])
  const convGroups = useMemo(() => {
    const m = new Map<string, { title: string; items: ShortTermItem[] }>()
    for (const it of data) {
      const g = m.get(it.conversation_id) ?? { title: it.conversation_title || '(제목 없음)', items: [] }
      g.items.push(it)
      m.set(it.conversation_id, g)
    }
    return [...m.entries()]
  }, [data])

  if (isLoading) return <div className="text-content-muted text-sm py-8 text-center">로딩 중...</div>
  if (isError) return <div className="text-accent-red text-sm py-8 text-center">단기 메모리를 불러오지 못했습니다</div>
  if (data.length === 0)
    return (
      <div className="text-center text-content-muted py-12 border border-dashed border-border rounded-xl">
        <Clock size={32} className="mx-auto mb-2 opacity-50" />
        <p className="text-sm">저장된 단기 메모리가 없습니다.</p>
        <p className="text-xs mt-1">대화 중에만 필요한 임시 맥락(진행 중인 작업의 목표·결정 사항 등)이 여기에 잠시 저장됩니다.</p>
      </div>
    )

  const segBtn = (active: boolean) =>
    `flex items-center gap-1.5 px-3 py-1.5 text-xs border-none cursor-pointer ${active ? 'bg-accent-primary text-white' : 'bg-transparent text-content-secondary hover:text-content-primary'}`

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex rounded-md border border-border overflow-hidden">
          <button onClick={() => setMode('conv')} className={segBtn(mode === 'conv')}><MessageSquare size={12} />대화방별</button>
          <button onClick={() => setMode('topic')} className={segBtn(mode === 'topic')} title="AI 가 비슷한 주제끼리 묶습니다"><Layers size={12} />유사 내용별 (AI)</button>
        </div>
        {mode === 'topic' && (
          <button
            onClick={() => groupsQuery.refetch()}
            disabled={groupsQuery.isFetching}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-border bg-transparent text-xs text-content-secondary hover:text-content-primary cursor-pointer disabled:opacity-50"
          >
            <RefreshCw size={12} className={groupsQuery.isFetching ? 'animate-spin' : ''} />
            다시 묶기
          </button>
        )}
      </div>

      {mode === 'conv' ? (
        <div className="space-y-5">
          {convGroups.map(([cid, g]) => (
            <div key={cid} className="space-y-2">
              <Link to={`/chat/${cid}`} className="inline-flex items-center gap-1.5 text-[13px] text-content-secondary hover:text-content-primary no-underline" title="이 대화방으로 이동">
                <MessageSquare size={13} />
                <span className="truncate max-w-[480px]">{g.title}</span>
                <span className="text-[11px] text-content-muted">{g.items.length}개</span>
              </Link>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 items-start">
                {g.items.map((it) => (
                  <ItemCard key={it.key} it={it} onDelete={() => { if (confirm('이 단기 메모리를 삭제하시겠습니까?')) del.mutate({ conversation_id: it.conversation_id, key: it.key }) }} />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : groupsQuery.isFetching && !groupsQuery.data ? (
        <div className="flex items-center justify-center gap-2 text-content-muted text-sm py-10"><Loader2 size={16} className="animate-spin" />비슷한 내용끼리 묶는 중...</div>
      ) : groupsQuery.isError ? (
        <div className="text-center text-accent-red text-sm py-8">
          {errorText(groupsQuery.error, '묶지 못했습니다')}
          <div><button onClick={() => groupsQuery.refetch()} className="mt-2 text-xs text-accent-primary border-none bg-transparent cursor-pointer underline">다시 시도</button></div>
        </div>
      ) : (
        <div className="space-y-6">
          {(groupsQuery.data ?? [])
            .map((g) => ({ ...g, rows: g.items.map((r) => byRef.get(refKey(r.conversation_id, r.key))).filter((x): x is ShortTermItem => !!x) }))
            .filter((g) => g.rows.length > 0)
            .sort((a, b) => b.rows.length - a.rows.length)
            .map((g, gi) => {
              const convCount = new Set(g.rows.map((r) => r.conversation_id)).size
              return (
                <div key={gi} className="space-y-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Layers size={14} className="text-accent-primary" />
                    <span className="text-[14px] font-medium text-content-primary">{g.title || g.rows[0].key}</span>
                    <span className="text-[11px] text-content-muted">항목 {g.rows.length}개 · 대화 {convCount}개</span>
                    {g.rows.length >= 2 && (
                      <button
                        onClick={() => previewMut.mutate({ title: g.title, items: g.rows.map((r) => ({ conversation_id: r.conversation_id, key: r.key })) })}
                        disabled={previewMut.isPending}
                        title="이 그룹의 중복을 합쳐 정리합니다 (미리보기 후 적용)"
                        className="flex items-center gap-1 px-2.5 py-1 rounded-md border border-border bg-transparent text-xs text-content-secondary hover:text-content-primary cursor-pointer disabled:opacity-50"
                      >
                        {previewMut.isPending && previewMut.variables?.title === g.title ? <Loader2 size={12} className="animate-spin" /> : <GitMerge size={12} />}
                        병합
                      </button>
                    )}
                  </div>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 items-start">
                    {g.rows.map((it) => (
                      <ItemCard key={refKey(it.conversation_id, it.key)} it={it} showConv onDelete={() => { if (confirm('이 단기 메모리를 삭제하시겠습니까?')) del.mutate({ conversation_id: it.conversation_id, key: it.key }) }} />
                    ))}
                  </div>
                </div>
              )
            })}
        </div>
      )}

      {preview && (
        <MergeDialog
          preview={preview.data}
          busy={applyMut.isPending}
          error={mergeError}
          onClose={() => setPreview(null)}
          onApply={(merged) => applyMut.mutate(merged)}
        />
      )}
    </div>
  )
}

import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Clock, MessageSquare, Trash2 } from 'lucide-react'
import { memoryApi } from '../../api/memory'
import type { ShortTermItem } from '../../types/memory'

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

/**
 * 단기 메모리: 한 대화방에서만 쓰이는 임시 메모리. 저장하거나 갱신한 뒤 일정 시간(기본 7일)이 지나면 자동으로 사라진다.
 * 대화방별로 묶어 보여 주고, 항목을 지울 수 있다.
 */
export default function ShortTermMemoryList() {
  const qc = useQueryClient()
  const { data = [], isLoading, isError } = useQuery<ShortTermItem[]>({
    queryKey: ['short-term-memories'],
    queryFn: async () => (await memoryApi.listShortTermAll()).data,
    refetchInterval: 60_000, // 남은 시간이 줄어드는 것을 반영한다
  })
  const del = useMutation({
    mutationFn: ({ conversation_id, key }: { conversation_id: string; key: string }) => memoryApi.deleteShortTerm(conversation_id, key),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['short-term-memories'] }),
  })

  const groups = useMemo(() => {
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
  if (groups.length === 0)
    return (
      <div className="text-center text-content-muted py-12 border border-dashed border-border rounded-xl">
        <Clock size={32} className="mx-auto mb-2 opacity-50" />
        <p className="text-sm">저장된 단기 메모리가 없습니다.</p>
        <p className="text-xs mt-1">대화 중에만 필요한 임시 맥락(진행 중인 작업의 목표·결정 사항 등)이 여기에 잠시 저장됩니다.</p>
      </div>
    )

  return (
    <div className="space-y-5">
      {groups.map(([cid, g]) => (
        <div key={cid} className="space-y-2">
          <Link to={`/chat/${cid}`} className="inline-flex items-center gap-1.5 text-[13px] text-content-secondary hover:text-content-primary no-underline" title="이 대화방으로 이동">
            <MessageSquare size={13} />
            <span className="truncate max-w-[480px]">{g.title}</span>
            <span className="text-[11px] text-content-muted">{g.items.length}개</span>
          </Link>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 items-start">
            {g.items.map((it) => (
              <div key={it.key} className="rounded-xl p-4 bg-surface-secondary border border-border">
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
                  </div>
                  <button
                    onClick={() => { if (confirm('이 단기 메모리를 삭제하시겠습니까?')) del.mutate({ conversation_id: it.conversation_id, key: it.key }) }}
                    className="p-1.5 text-content-muted hover:text-accent-red transition-colors flex-shrink-0"
                    title="삭제"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

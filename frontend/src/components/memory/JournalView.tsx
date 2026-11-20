import { useState } from 'react'
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Pencil, Trash2 } from 'lucide-react'
import { memoryApi } from '../../api/memory'
import { T } from '../skills/typography'
import { errorText, inputCls, primaryBtn } from '../skills/common'
import type { JournalDay } from '../../types/memory'

const today = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10)

/** Episodes: 날짜별 일지 (영구 보관). 저장된 사건·해결 사례가 그날 일지에 한 줄씩 쌓이고, 직접 고치거나 메모를 덧붙일 수 있다. */
export default function JournalView() {
  const qc = useQueryClient()
  const { data, fetchNextPage, hasNextPage, isLoading } = useInfiniteQuery({
    queryKey: ['memory-journal'],
    queryFn: async ({ pageParam }) => (await memoryApi.listJournal(pageParam)).data,
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last: JournalDay[]) => (last.length >= 30 ? last[last.length - 1].day : undefined),
  })
  const days = (data?.pages ?? []).flat()
  const [editing, setEditing] = useState<{ day: string; text: string } | null>(null)
  const [error, setError] = useState('')
  const refresh = () => qc.invalidateQueries({ queryKey: ['memory-journal'] })
  const save = useMutation({
    mutationFn: (v: { day: string; text: string }) => memoryApi.saveJournal(v.day, v.text),
    onSuccess: () => { setEditing(null); setError(''); refresh() },
    onError: (e) => setError(errorText(e, '저장하지 못했습니다')),
  })
  const del = useMutation({
    mutationFn: (day: string) => memoryApi.deleteJournal(day),
    onSuccess: refresh,
    onError: (e) => setError(errorText(e, '삭제하지 못했습니다')),
  })

  return (
    <div className="space-y-3 max-w-[760px]">
      <p className={T.itemDesc}>
        날짜별 일지(Episodes)입니다. 대화에서 저장된 사건·해결 사례가 그날 일지에 한 줄씩 쌓이고, 사례 메모리가 오래돼 정리되어도 일지는 남습니다.
        에이전트도 일지를 읽고 오늘 일지에 메모를 남길 수 있습니다.
      </p>
      <button onClick={() => setEditing({ day: today(), text: days.find((d) => d.day === today())?.content ?? '' })} className={primaryBtn}>오늘 메모 쓰기</button>
      {error && <div className="text-[13px] text-red-500">{error}</div>}
      {isLoading && <p className={T.itemDesc}>불러오는 중…</p>}
      {!isLoading && days.length === 0 && <p className={T.itemDesc}>아직 일지가 없습니다.</p>}
      <ul className="space-y-3">
        {days.map((d) => (
          <li key={d.day} className="bg-surface-secondary border border-border rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className={T.itemTitle}>{d.day}</h3>
              <div className="flex gap-1">
                <button onClick={() => setEditing({ day: d.day, text: d.content })} title="수정" aria-label="수정" className="p-1.5 text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer"><Pencil size={14} /></button>
                <button onClick={() => { if (confirm(`${d.day} 일지를 삭제할까요?`)) del.mutate(d.day) }} title="삭제" aria-label="삭제" className="p-1.5 text-content-secondary hover:text-accent-red border-none bg-transparent cursor-pointer"><Trash2 size={14} /></button>
              </div>
            </div>
            <pre className="whitespace-pre-wrap font-sans text-[13px] text-content-secondary m-0">{d.content}</pre>
          </li>
        ))}
      </ul>
      {hasNextPage && <button onClick={() => fetchNextPage()} className="text-[13px] text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer">이전 일지 더 보기</button>}

      {editing && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onMouseDown={(e) => { if (e.target === e.currentTarget) setEditing(null) }}>
          <div role="dialog" aria-modal="true" className="bg-surface-primary border border-border rounded-xl shadow-xl w-full max-w-[640px] p-5 space-y-3">
            <h3 className={T.section}>{editing.day} 일지</h3>
            <textarea value={editing.text} onChange={(e) => setEditing({ ...editing, text: e.target.value })} rows={10} maxLength={20000} autoFocus className={`${inputCls} text-[13px] resize-y`} placeholder="- 14:30 오늘 있었던 일" />
            <p className="text-xs text-content-tertiary">내용을 모두 지우고 저장하면 그날 일지가 삭제됩니다.</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setEditing(null)} className="px-3 py-2 rounded-md text-[13px] text-content-secondary bg-transparent border border-border cursor-pointer">취소</button>
              <button onClick={() => save.mutate({ day: editing.day, text: editing.text })} disabled={save.isPending} className={primaryBtn}>{save.isPending ? '저장 중...' : '저장'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

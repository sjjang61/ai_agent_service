import { useState } from 'react'
import { Loader2, Trash2, X } from 'lucide-react'
import type { CalendarEvent, EventInput } from '../api/calendar'

const inputCls = 'w-full px-3 py-2 bg-surface-primary border border-border rounded-lg text-sm text-content-primary focus:outline-none focus:border-accent-primary'

/** 일정 추가/수정 대화상자. event 가 있으면 수정, 없으면 initialDate 날짜로 새 일정. */
export default function CalendarEventDialog({ event, initialDate, onClose, onSave, onDelete }: {
  event?: CalendarEvent | null
  initialDate: string
  onClose: () => void
  onSave: (input: EventInput) => Promise<void>
  onDelete?: () => Promise<void>
}) {
  const [f, setF] = useState<EventInput>({
    title: event?.title ?? '',
    start_date: event?.start_date ?? initialDate,
    end_date: event?.end_date ?? initialDate,
    start_time: event?.start_time ?? '',
    end_time: event?.end_time ?? '',
    note: event?.note ?? '',
    save_to_memory: event?.in_memory ?? false,
  })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const set = <K extends keyof EventInput>(k: K, v: EventInput[K]) => setF((p) => ({ ...p, [k]: v }))

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setErr(null)
    try { await fn(); onClose() } catch (e) {
      const d = (e as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
      setErr(typeof d === 'string' ? d : Array.isArray(d) ? d.map((x: { msg?: string }) => x.msg).join(', ') : '저장하지 못했습니다.')
    } finally { setBusy(false) }
  }
  const valid = f.title.trim() && f.start_date && f.end_date >= f.start_date

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="w-full max-w-md bg-surface-secondary border border-border rounded-xl p-5 space-y-3" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center">
          <h3 className="flex-1 text-[16px] font-semibold text-content-primary">{event ? '일정 수정' : '일정 추가'}</h3>
          <button onClick={onClose} aria-label="닫기" className="p-1 text-content-muted hover:text-content-primary"><X size={16} /></button>
        </div>
        <input autoFocus className={inputCls} placeholder="제목" value={f.title} maxLength={200} onChange={(e) => set('title', e.target.value)} />
        <div className="grid grid-cols-2 gap-2">
          <label className="text-xs text-content-muted">시작일
            <input type="date" className={`${inputCls} mt-1`} value={f.start_date} onChange={(e) => setF((p) => ({ ...p, start_date: e.target.value, end_date: p.end_date < e.target.value ? e.target.value : p.end_date }))} />
          </label>
          <label className="text-xs text-content-muted">종료일
            <input type="date" className={`${inputCls} mt-1`} value={f.end_date} min={f.start_date} onChange={(e) => set('end_date', e.target.value)} />
          </label>
          <label className="text-xs text-content-muted">시작 시각 (선택)
            <input type="time" className={`${inputCls} mt-1`} value={f.start_time} onChange={(e) => set('start_time', e.target.value)} />
          </label>
          <label className="text-xs text-content-muted">종료 시각 (선택)
            <input type="time" className={`${inputCls} mt-1`} value={f.end_time} onChange={(e) => set('end_time', e.target.value)} />
          </label>
        </div>
        <textarea className={`${inputCls} resize-none`} rows={3} placeholder="메모 (인원, 장소, 항공편 등)" value={f.note} onChange={(e) => set('note', e.target.value)} />
        <label className="flex items-start gap-2 text-[13px] text-content-secondary cursor-pointer">
          <input type="checkbox" className="mt-0.5" checked={f.save_to_memory} onChange={(e) => set('save_to_memory', e.target.checked)} />
          <span>메모리에도 저장<span className="block text-xs text-content-tertiary">에이전트가 이 일정을 알고 답하도록 사실 메모리로 저장하며, 종료일이 지나면 자동으로 사라집니다.</span></span>
        </label>
        {err && <p className="text-xs text-accent-red">{err}</p>}
        <div className="flex items-center gap-2 pt-1">
          {event && onDelete && (
            <button disabled={busy} onClick={() => confirm('이 일정을 삭제하시겠습니까?' + (event.in_memory ? '\n연결된 메모리도 함께 삭제됩니다.' : '')) && run(onDelete)}
              className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm text-accent-red hover:bg-accent-red/10"><Trash2 size={14} /> 삭제</button>
          )}
          <div className="flex-1" />
          <button onClick={onClose} className="px-3 py-2 rounded-lg text-sm text-content-muted hover:text-content-primary">취소</button>
          <button disabled={!valid || busy} onClick={() => run(() => onSave(f))}
            className="flex items-center gap-1 px-4 py-2 rounded-lg text-sm bg-accent-primary text-white disabled:opacity-50">
            {busy && <Loader2 size={14} className="animate-spin" />} 저장
          </button>
        </div>
      </div>
    </div>
  )
}

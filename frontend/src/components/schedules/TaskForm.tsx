import { useMemo, useState } from 'react'
import { Loader2, TriangleAlert } from 'lucide-react'
import type { TaskInput } from '../../types/schedule'
import { SCHEDULE_TYPE_OPTIONS, WEEKDAY_LABELS, allTimezones, errorText } from './scheduleUtils'

interface Props {
  mode: 'create' | 'edit'
  initial: TaskInput
  onSubmit: (input: TaskInput) => Promise<void>
  onCancel: () => void
}

const inputCls =
  'w-full px-3.5 py-2.5 bg-surface-primary border border-border rounded-[var(--radius-md)] text-[13px] text-content-primary placeholder:text-content-muted focus:outline-none focus:border-accent-primary transition-colors'

/** ISO(UTC) → <input type="datetime-local"> 값(내 컴퓨터 시간대) */
function toLocalInput(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="block text-[13px] font-medium text-content-primary">{label}</label>
      {children}
      {hint && <p className="text-xs text-content-tertiary">{hint}</p>}
    </div>
  )
}

function Check({ checked, onChange, label, hint }: { checked: boolean; onChange: (v: boolean) => void; label: string; hint: string }) {
  return (
    <label className="flex items-start gap-2.5 cursor-pointer">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="mt-1" />
      <span>
        <span className="block text-[13px] text-content-primary">{label}</span>
        <span className="block text-xs text-content-tertiary">{hint}</span>
      </span>
    </label>
  )
}

export default function TaskForm({ mode, initial, onSubmit, onCancel }: Props) {
  const [v, setV] = useState<TaskInput>(initial)
  const [onceLocal, setOnceLocal] = useState(toLocalInput(initial.run_at))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const zones = useMemo(allTimezones, [])
  const set = <K extends keyof TaskInput>(k: K, val: TaskInput[K]) => setV((s) => ({ ...s, [k]: val }))

  const t = v.schedule_type
  const needsTime = t === 'daily' || t === 'weekdays' || t === 'weekly' || t === 'monthly'

  const toggleDay = (d: number) => {
    const cur = v.weekdays ?? []
    set('weekdays', cur.includes(d) ? cur.filter((x) => x !== d) : [...cur, d].sort())
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (t === 'once' && !onceLocal) {
      setError('실행할 날짜와 시각을 입력하세요')
      return
    }
    setSubmitting(true)
    try {
      await onSubmit({ ...v, run_at: t === 'once' ? new Date(onceLocal).toISOString() : null })
    } catch (err) {
      setError(errorText(err))
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="max-w-[640px] mx-auto p-6 space-y-5">
      <h2 className="text-[17px] font-semibold text-content-primary">{mode === 'create' ? '새 작업' : '작업 편집'}</h2>

      <Field label="이름">
        <input value={v.name} onChange={(e) => set('name', e.target.value)} maxLength={200} placeholder="예: 아침 뉴스 브리핑" className={inputCls} required />
      </Field>

      <Field label="할 일" hint="에이전트에게 시킬 일을 평소 대화하듯 적으세요. 같은 대화에 결과가 쌓이므로 '지난번과 비교' 같은 요청도 가능합니다.">
        <textarea
          value={v.prompt}
          onChange={(e) => set('prompt', e.target.value)}
          rows={6}
          maxLength={4000}
          placeholder="예: 오늘 AI 분야 주요 뉴스를 5개로 요약하고 출처 링크를 붙여줘."
          className={`${inputCls} resize-y leading-relaxed`}
          required
        />
        <div className="text-right text-[11px] text-content-muted">{v.prompt.length} / 4000</div>
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <Field label="반복">
          <select value={t} onChange={(e) => set('schedule_type', e.target.value as TaskInput['schedule_type'])} className={inputCls}>
            {SCHEDULE_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </Field>
        {needsTime && (
          <Field label="시각">
            <input type="time" value={v.schedule_time ?? ''} onChange={(e) => set('schedule_time', e.target.value)} className={inputCls} required />
          </Field>
        )}
        {t === 'interval' && (
          <Field label="간격 (시간)" hint="최소 1시간">
            <input type="number" min={1} max={168} value={v.interval_hours ?? ''} onChange={(e) => set('interval_hours', Number(e.target.value))} className={inputCls} required />
          </Field>
        )}
        {t === 'monthly' && (
          <Field label="일자" hint="짧은 달은 말일에 실행">
            <input type="number" min={1} max={31} value={v.day_of_month ?? ''} onChange={(e) => set('day_of_month', Number(e.target.value))} className={inputCls} required />
          </Field>
        )}
        {t === 'once' && (
          <Field label="날짜·시각" hint="내 컴퓨터 시간대 기준">
            <input type="datetime-local" value={onceLocal} onChange={(e) => setOnceLocal(e.target.value)} className={inputCls} required />
          </Field>
        )}
      </div>

      {t === 'weekly' && (
        <Field label="요일">
          <div className="flex gap-1.5">
            {WEEKDAY_LABELS.map((label, d) => {
              const on = (v.weekdays ?? []).includes(d)
              return (
                <button
                  key={d}
                  type="button"
                  onClick={() => toggleDay(d)}
                  className={`w-9 h-9 rounded-full text-[13px] border transition-colors ${
                    on ? 'bg-accent-primary border-accent-primary text-white' : 'bg-surface-primary border-border text-content-secondary hover:bg-surface-hover'
                  }`}
                >
                  {label}
                </button>
              )
            })}
          </div>
        </Field>
      )}

      {needsTime && (
        <Field label="시간대" hint="이 시간대의 시각 기준으로 실행됩니다 (서머타임 자동 반영)">
          <input list="schedule-timezones" value={v.timezone} onChange={(e) => set('timezone', e.target.value)} className={inputCls} />
          <datalist id="schedule-timezones">
            {zones.map((z) => (
              <option key={z} value={z} />
            ))}
          </datalist>
        </Field>
      )}

      <div className="space-y-3 pt-1">
        <Check checked={v.new_conversation_each_run} onChange={(x) => set('new_conversation_each_run', x)} label="실행마다 새 대화로 저장" hint="끄면 한 대화에 결과가 이어져서 이전 결과와 비교할 수 있습니다." />
        <Check checked={v.allow_mcp} onChange={(x) => set('allow_mcp', x)} label="MCP 도구 사용 허용" hint="사람이 지켜보지 않는 실행에서 외부 서비스를 호출할 수 있습니다. 필요한 작업에만 켜세요." />
        <Check checked={v.allow_browser} onChange={(x) => set('allow_browser', x)} label="브라우저 에이전트 사용 허용" hint="로그인·클릭 같은 웹 조작이 필요한 작업에만 켜세요." />
      </div>

      <div className="flex gap-2 rounded-[var(--radius-md)] border border-border bg-surface-secondary px-3.5 py-3 text-xs text-content-secondary">
        <TriangleAlert size={14} className="flex-shrink-0 mt-0.5 text-accent-amber" />
        <span>할 일(프롬프트)은 서버에 그대로 저장됩니다. 비밀번호나 API 키는 적지 마세요. 예약 실행은 질문 없이 끝까지 진행하며, 연속 3회 실패하면 자동으로 일시중지됩니다.</span>
      </div>

      {error && <p className="text-[13px] text-accent-red">{error}</p>}

      <div className="flex justify-end gap-2 pt-1">
        <button type="button" onClick={onCancel} className="px-4 py-2.5 rounded-[var(--radius-md)] text-[13px] text-content-secondary hover:bg-surface-hover transition-colors">
          취소
        </button>
        <button
          type="submit"
          disabled={submitting}
          className="flex items-center gap-2 px-5 py-2.5 bg-accent-primary hover:bg-accent-hover disabled:opacity-40 text-white rounded-[var(--radius-md)] text-[13px] font-medium transition-colors"
        >
          {submitting && <Loader2 size={14} className="animate-spin" />}
          {mode === 'create' ? '만들기' : '저장'}
        </button>
      </div>
    </form>
  )
}

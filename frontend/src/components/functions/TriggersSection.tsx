import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Clock, Copy, Link2, Loader2, Trash2 } from 'lucide-react'
import { driveError } from '../../api/drive'
import { functionsApi, webhookUrl, type FnDetail, type FnTrigger, type ScheduleType } from '../../api/functions'
import { formatDateTimeMinute } from '../../utils/time'

const input = 'px-2.5 py-1.5 rounded-lg border border-border bg-surface-secondary text-xs text-content-primary'
const btn = 'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border border-border bg-surface-secondary text-content-primary hover:bg-surface-hover cursor-pointer disabled:opacity-50'
const DAYS = ['월', '화', '수', '목', '금', '토', '일']
const TYPES: [ScheduleType, string][] = [['daily', '매일'], ['weekdays', '평일'], ['weekly', '매주'], ['monthly', '매월'], ['interval', '반복(N시간마다)'], ['once', '한 번']]

export function TriggerRow({ t, fnName, onChanged, onRegenerated }: { t: FnTrigger; fnName?: string; onChanged: () => void; onRegenerated?: (t: FnTrigger) => void }) {
  const [err, setErr] = useState<string | null>(null)
  const toggle = useMutation({ mutationFn: (v: boolean) => functionsApi.setTriggerEnabled(t.id, v), onSuccess: onChanged, onError: (e) => setErr(driveError(e, '바꾸지 못했습니다')) })
  const del = useMutation({ mutationFn: () => functionsApi.removeTrigger(t.id), onSuccess: onChanged, onError: (e) => setErr(driveError(e, '삭제하지 못했습니다')) })
  const regen = useMutation({ mutationFn: () => functionsApi.regenerateHook(t.id), onSuccess: (r) => { onChanged(); onRegenerated?.(r) }, onError: (e) => setErr(driveError(e, '재발급하지 못했습니다')) })
  return (
    <li className="py-2.5 border-b last:border-b-0 border-border text-xs">
      <div className="flex items-center gap-2">
        {t.kind === 'schedule' ? <Clock size={14} className="text-content-tertiary flex-shrink-0" aria-label="예약" /> : <Link2 size={14} className="text-content-tertiary flex-shrink-0" aria-label="웹훅" />}
        <div className="flex-1 min-w-0">
          <div className="text-content-primary">
            {fnName && <span className="font-medium mr-1.5">{fnName}</span>}
            {t.kind === 'schedule' ? t.description : '웹훅'}{t.name && <span className="ml-1.5 text-content-tertiary">· {t.name}</span>}
            <span className="ml-1.5 px-1.5 py-0.5 rounded bg-surface-tertiary text-content-secondary">{t.ref}</span>
          </div>
          <div className="text-content-tertiary">
            {t.kind === 'schedule' ? (t.enabled && t.next_run_at ? `다음 실행 ${formatDateTimeMinute(t.next_run_at)}` : '예정 없음') : (t.last_called_at ? `마지막 호출 ${formatDateTimeMinute(t.last_called_at)}` : '아직 호출되지 않음')}
            {t.last_status && <span className={t.last_status.startsWith('실행하지 못함') || t.last_status.includes('멈췄') ? 'text-accent-red' : ''}> · {t.last_status}</span>}
          </div>
        </div>
        {t.kind === 'webhook' && <button onClick={() => confirm('토큰을 새로 만들면 지금 쓰는 주소는 즉시 쓸 수 없게 됩니다. 계속할까요?') && regen.mutate()} disabled={regen.isPending} className={btn}>{regen.isPending ? <Loader2 size={12} className="animate-spin" /> : null} 주소 재발급</button>}
        <button role="switch" aria-checked={t.enabled} aria-label={`${t.kind === 'schedule' ? '예약' : '웹훅'} ${t.enabled ? '끄기' : '켜기'}`} onClick={() => toggle.mutate(!t.enabled)} disabled={toggle.isPending}
          className={`w-9 h-5 rounded-full border-none cursor-pointer relative transition-colors ${t.enabled ? 'bg-accent-primary' : 'bg-surface-tertiary'}`}>
          <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${t.enabled ? 'left-[18px]' : 'left-0.5'}`} />
        </button>
        <button onClick={() => confirm('이 트리거를 삭제할까요?') && del.mutate()} aria-label="트리거 삭제" className="border-none bg-transparent text-content-muted hover:text-accent-red cursor-pointer"><Trash2 size={14} /></button>
      </div>
      {err && <p role="alert" className="m-0 mt-1 text-accent-red">{err}</p>}
    </li>
  )
}

/** 함수 상세의 트리거 섹션: 예약(주기 실행)과 웹훅(주소로 호출)을 만들고 켜고 끄고 지운다. 트리거는 별칭을 가리키는 것을 권장한다. */
export default function TriggersSection({ fn }: { fn: FnDetail }) {
  const qc = useQueryClient()
  const { data: triggers = [], isLoading } = useQuery({ queryKey: ['fn-triggers', fn.id], queryFn: () => functionsApi.triggers(fn.id), retry: false })
  const refresh = () => { qc.invalidateQueries({ queryKey: ['fn-triggers'] }); qc.invalidateQueries({ queryKey: ['fn-all-triggers'] }) }
  const [kind, setKind] = useState<'schedule' | 'webhook'>('schedule')
  const [name, setName] = useState('')
  const [ref, setRef] = useState('latest')
  const [type, setType] = useState<ScheduleType>('daily')
  const [time, setTime] = useState('09:00')
  const [weekdays, setWeekdays] = useState<number[]>([0])
  const [dom, setDom] = useState(1)
  const [hours, setHours] = useState(6)
  const [runAt, setRunAt] = useState('')
  const [created, setCreated] = useState<FnTrigger | null>(null)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: () => {
      if (kind === 'webhook') return functionsApi.createTrigger(fn.id, { kind, name, ref })
      return functionsApi.createTrigger(fn.id, {
        kind, name, ref, schedule_type: type, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Seoul',
        ...(type === 'interval' ? { interval_hours: hours } : {}),
        ...(type === 'once' ? { run_at: runAt ? new Date(runAt).toISOString() : undefined } : {}),
        ...(['daily', 'weekdays', 'weekly', 'monthly'].includes(type) ? { schedule_time: time } : {}),
        ...(type === 'weekly' ? { weekdays } : {}), ...(type === 'monthly' ? { day_of_month: dom } : {}),
      })
    },
    onSuccess: (t) => { setError(null); setName(''); refresh(); if (t.kind === 'webhook') { setCreated(t); setCopied(false) } },
    onError: (e) => setError(driveError(e, '트리거를 만들지 못했습니다')),
  })
  const aliases = Object.keys(fn.aliases).filter((a) => a !== 'latest')
  const url = created?.path ? webhookUrl(created.path) : ''
  const copy = async () => { try { await navigator.clipboard.writeText(url); setCopied(true); window.setTimeout(() => setCopied(false), 1500) } catch { setError('복사하지 못했습니다. 주소를 직접 선택해 복사하세요') } }

  return (
    <section className="rounded-xl border border-border bg-surface-primary p-4" aria-label="트리거">
      <h2 className="m-0 mb-3 text-sm font-semibold text-content-primary">트리거 <span className="font-normal text-xs text-content-tertiary">정해진 시각이나 웹훅 호출로 자동 실행합니다. 별칭을 가리키면 새 버전이 나와도 바뀌지 않습니다</span></h2>
      {created?.path && (
        <div role="status" className="mb-3 p-3 rounded-lg border border-accent-amber/40 bg-accent-amber/10 text-xs">
          <div className="font-medium text-content-primary">웹훅 주소를 만들었습니다. 이 주소는 지금만 볼 수 있으니 안전한 곳에 보관하세요.</div>
          <div className="mt-2 flex items-center gap-1.5"><input readOnly value={url} onFocus={(e) => e.currentTarget.select()} aria-label="웹훅 주소" className={`${input} flex-1 font-mono`} />
            <button onClick={copy} className={btn}>{copied ? <Check size={12} /> : <Copy size={12} />} {copied ? '복사됨' : '복사'}</button></div>
          <pre className="m-0 mt-2 p-2 rounded bg-surface-secondary text-[11px] font-mono whitespace-pre-wrap break-all text-content-secondary">{`curl -X POST '${url}' -H 'Content-Type: application/json' -d '{"name":"world"}'`}</pre>
          <button onClick={() => setCreated(null)} className="mt-2 border-none bg-transparent p-0 text-xs text-content-secondary underline cursor-pointer">닫기</button>
        </div>
      )}
      {isLoading ? <p className="m-0 text-xs text-content-muted">불러오는 중...</p> : triggers.length === 0 ? <p className="m-0 mb-3 text-xs text-content-muted">등록된 트리거가 없습니다</p> : (
        <ul className="m-0 mb-3 p-0 list-none">{triggers.map((t) => <TriggerRow key={t.id} t={t} onChanged={refresh} onRegenerated={(r) => { setCreated(r); setCopied(false) }} />)}</ul>
      )}
      <div className="pt-3 border-t border-border space-y-2">
        <div className="flex items-center gap-2 text-xs" role="radiogroup" aria-label="트리거 종류">
          {(['schedule', 'webhook'] as const).map((k) => <label key={k} className="flex items-center gap-1 cursor-pointer text-content-primary"><input type="radio" name="trigger-kind" checked={kind === k} onChange={() => setKind(k)} /> {k === 'schedule' ? '예약 추가' : '웹훅 추가'}</label>)}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="이름 (선택)" aria-label="트리거 이름" maxLength={100} className={`${input} w-32`} />
          <select aria-label="실행할 버전" value={ref} onChange={(e) => setRef(e.target.value)} className={input}>
            <option value="latest">latest (v{fn.latest_version})</option>
            {aliases.map((a) => <option key={a} value={a}>{a} (v{fn.aliases[a]}) · 권장</option>)}
            {fn.versions.map((v) => <option key={v.version} value={String(v.version)}>v{v.version}</option>)}
          </select>
          {kind === 'schedule' && <>
            <select aria-label="반복 종류" value={type} onChange={(e) => setType(e.target.value as ScheduleType)} className={input}>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
            {['daily', 'weekdays', 'weekly', 'monthly'].includes(type) && <input type="time" aria-label="실행 시각" value={time} onChange={(e) => setTime(e.target.value)} className={input} />}
            {type === 'interval' && <label className="flex items-center gap-1 text-xs text-content-secondary"><input type="number" min={1} max={168} aria-label="반복 간격(시간)" value={hours} onChange={(e) => setHours(Number(e.target.value))} className={`${input} w-16`} /> 시간마다</label>}
            {type === 'monthly' && <label className="flex items-center gap-1 text-xs text-content-secondary"><input type="number" min={1} max={31} aria-label="일자" value={dom} onChange={(e) => setDom(Number(e.target.value))} className={`${input} w-16`} /> 일</label>}
            {type === 'once' && <input type="datetime-local" aria-label="실행 일시" value={runAt} onChange={(e) => setRunAt(e.target.value)} className={input} />}
          </>}
          <button onClick={() => create.mutate()} disabled={create.isPending || (kind === 'schedule' && type === 'once' && !runAt) || (kind === 'schedule' && type === 'weekly' && weekdays.length === 0)} className={btn}>{create.isPending && <Loader2 size={12} className="animate-spin" />} 만들기</button>
        </div>
        {kind === 'schedule' && type === 'weekly' && (
          <div className="flex items-center gap-1" role="group" aria-label="요일">{DAYS.map((d, i) => (
            <label key={d} className={`px-2 py-1 rounded-lg border text-xs cursor-pointer ${weekdays.includes(i) ? 'border-accent-primary bg-accent-primary/15 text-content-primary' : 'border-border text-content-secondary'}`}>
              <input type="checkbox" className="sr-only" checked={weekdays.includes(i)} onChange={() => setWeekdays((w) => (w.includes(i) ? w.filter((x) => x !== i) : [...w, i].sort()))} />{d}</label>))}</div>
        )}
        {error && <p role="alert" className="m-0 text-xs text-accent-red">{error}</p>}
      </div>
    </section>
  )
}

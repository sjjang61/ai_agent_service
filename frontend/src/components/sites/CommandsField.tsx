import { useState } from 'react'
import { inputCls } from '../skills/common'
import { Field } from './fields'

export interface RefCommand { skill: string; label: string; command: string }

/** 분석 전에 일회용 컨테이너에서 돌릴 조회 전용 스킬 명령(JSON). 결과가 기준 데이터로 분석 프롬프트에 붙는다. */
export default function CommandsField({ value, onChange }: { value: RefCommand[]; onChange: (v: RefCommand[]) => void }) {
  const [text, setText] = useState(() => (value.length ? JSON.stringify(value, null, 2) : ''))
  const [err, setErr] = useState('')
  const edit = (t: string) => {
    setText(t)
    if (!t.trim()) { setErr(''); onChange([]); return }
    try {
      const v = JSON.parse(t)
      if (!Array.isArray(v)) throw new Error('목록([ ... ])이어야 합니다')
      setErr(''); onChange(v)
    } catch (e) { setErr(`JSON 형식이 올바르지 않습니다: ${(e as Error).message}`) }
  }
  return (
    <Field
      label="사전 실행 명령 (고급)"
      hint={'분석·검증 전에 사용자의 스킬 폴더를 읽기 전용으로 붙인 일회용 컨테이너에서 조회 전용 명령을 돌려 결과를 기준 데이터로 줍니다. 입력값은 {from} {date:ymd}(YYYYMMDD) {date:iso} 처럼 쓰고, 필요한 입력이 없거나 실패하면 건너뜁니다. 예: [{"skill":"railway-timetable","label":"코레일 시간표","command":"uv run --script scripts/railway_timetable.py search --dep {from} --arr {to} --date {date:ymd}"}]'}
    >
      <div className="space-y-1">
        <textarea value={text} onChange={(e) => edit(e.target.value)} rows={text ? 8 : 3} spellCheck={false} className={`${inputCls} resize-y font-mono text-[12.5px]`} placeholder="비워 두면 사전 실행 없음" />
        {err && <p className="text-xs text-red-500">{err}</p>}
      </div>
    </Field>
  )
}

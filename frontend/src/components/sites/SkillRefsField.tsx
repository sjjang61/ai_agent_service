import { useQuery } from '@tanstack/react-query'
import { skillsApi } from '../../api/skills'
import type { Skill } from '../../types/skill'
import { inputCls } from '../skills/common'
import { Field } from './fields'

/** 사이트 분석이 참고할 스킬 이름(쉼표). 내가 가진 스킬이면 '있음', 아니면 '없음(건너뜀)'으로 알려 준다. */
export default function SkillRefsField({ value, onChange, scope }: { value: string; onChange: (v: string) => void; scope: '분야' | '사이트' }) {
  const { data: all = [] } = useQuery<Skill[]>({ queryKey: ['skills'], queryFn: async () => (await skillsApi.list()).data })
  const names = value.split(',').map((s) => s.trim()).filter(Boolean)
  const have = new Set(all.filter((s) => s.is_active).map((s) => s.name.toLowerCase()))
  return (
    <Field
      label="참고 스킬"
      hint={`쉼표로 구분(예: railway-timetable). 이 ${scope}를 분석·검증할 때 내가 가진 스킬이면 그 설명을 참고 자료로 받습니다. 없는 스킬은 건너뛰고 지금처럼 분석합니다. 스킬 내용이 화면과 다르면 화면이 우선입니다.`}
    >
      <div className="space-y-1.5">
        <input value={value} onChange={(e) => onChange(e.target.value)} className={inputCls} placeholder="예: railway-timetable" />
        {names.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {names.map((n) => (
              <span key={n} className={`text-xs px-2 py-0.5 rounded-full border ${have.has(n.toLowerCase()) ? 'border-green-600/40 text-green-600' : 'border-border text-content-tertiary'}`}>
                {n} · {have.has(n.toLowerCase()) ? '있음' : '없음(건너뜀)'}
              </span>
            ))}
          </div>
        )}
      </div>
    </Field>
  )
}

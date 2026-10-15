import { useState } from 'react'
import axios from 'axios'
import { MessageCircleQuestion } from 'lucide-react'
import { chatApi } from '../../api/chat'
import type { AgentStepData } from '../../types/chat'

interface Question {
  id: string
  type: 'single_choice' | 'multi_choice' | 'text'
  label: string
  required: boolean
  options?: string[]
  allow_other?: boolean
  placeholder?: string
}

export interface FormRequest {
  title: string
  description?: string
  questions: Question[]
  /** 응답 상태: pending(대기) | answered | cancelled | timeout | invalid */
  state: 'pending' | 'answered' | 'cancelled' | 'timeout' | 'invalid'
  answers?: Record<string, string | string[]>
}

function normalize(input: unknown): Pick<FormRequest, 'title' | 'description' | 'questions'> | null {
  const i = input as { title?: unknown; description?: unknown; questions?: unknown }
  if (!i || !Array.isArray(i.questions) || i.questions.length === 0) return null
  const questions: Question[] = []
  for (const [idx, raw] of (i.questions as Record<string, unknown>[]).entries()) {
    const type = raw?.type
    if (type !== 'single_choice' && type !== 'multi_choice' && type !== 'text') return null
    const options = Array.isArray(raw.options) ? raw.options.map(String) : undefined
    if (type !== 'text' && (!options || options.length < 2)) return null
    questions.push({
      id: String(raw.id ?? `q${idx + 1}`),
      type,
      label: String(raw.label ?? ''),
      required: raw.required !== false,
      options,
      allow_other: Boolean(raw.allow_other),
      placeholder: raw.placeholder ? String(raw.placeholder) : undefined,
    })
  }
  return { title: String(i.title ?? '질문'), description: i.description ? String(i.description) : undefined, questions }
}

/** 메시지의 스텝에서 가장 최근 form_ask_user 요청과 응답 상태를 꺼낸다. */
export function extractLatestForm(steps: AgentStepData[] | undefined): FormRequest | null {
  const list = steps ?? []
  let callIdx = -1
  for (let i = list.length - 1; i >= 0; i--) {
    if (list[i].type === 'tool_call' && list[i].tool === 'form_ask_user') {
      callIdx = i
      break
    }
  }
  if (callIdx < 0) return null
  const spec = normalize(list[callIdx].input)
  if (!spec) return null
  const result = list.slice(callIdx + 1).find((s) => s.type === 'tool_result' && s.tool === 'form_ask_user')
  if (!result) return { ...spec, state: 'pending' }
  const out = result.output ?? ''
  try {
    const p = JSON.parse(out)
    if (p.answers) return { ...spec, state: 'answered', answers: p.answers }
    if (p.cancelled) return { ...spec, state: 'cancelled' }
    if (p.timeout) return { ...spec, state: 'timeout' }
  } catch {
    // JSON 이 아니면 검증 오류("Error: ...")
  }
  return { ...spec, state: 'invalid' }
}

export default function FormCard({
  form,
  conversationId,
  interactive,
}: {
  form: FormRequest
  conversationId: string
  interactive: boolean
}) {
  const [values, setValues] = useState<Record<string, string | string[]>>({})
  const [others, setOthers] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)

  if (form.state === 'invalid') return null
  const active = form.state === 'pending' && interactive && !sent

  const submit = async (cancelled: boolean) => {
    setBusy(true)
    setError(null)
    try {
      const answers: Record<string, string | string[]> = {}
      for (const q of form.questions) {
        const v = values[q.id]
        const other = others[q.id]?.trim()
        if (q.type === 'multi_choice') {
          const arr = [...((v as string[]) ?? []), ...(other ? [other] : [])]
          if (arr.length) answers[q.id] = arr
        } else {
          const val = other || (v as string) || ''
          if (val) answers[q.id] = val
        }
      }
      await chatApi.answerForm(conversationId, cancelled ? { cancelled: true } : { answers })
      setSent(true)
    } catch (e) {
      const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null
      setError(typeof detail === 'string' ? detail : '응답을 전달하지 못했습니다')
    } finally {
      setBusy(false)
    }
  }

  const answered = form.state === 'answered' ? form.answers ?? {} : null
  const toggle = (qid: string, opt: string) =>
    setValues((s) => {
      const cur = (s[qid] as string[]) ?? []
      return { ...s, [qid]: cur.includes(opt) ? cur.filter((x) => x !== opt) : [...cur, opt] }
    })

  return (
    <div className="mb-3 rounded-[var(--radius-lg)] border border-accent-blue/30 bg-surface-secondary p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-2">
        <MessageCircleQuestion size={16} className="text-accent-blue" />
        <h4 className="text-sm font-semibold text-content-primary">{form.title}</h4>
      </div>
      {form.description && <p className="text-xs text-content-secondary mb-3">{form.description}</p>}

      <div className="space-y-3 mt-2">
        {form.questions.map((q) => (
          <div key={q.id} className="p-3 rounded-md bg-surface-tertiary/50">
            <p className="text-sm text-content-primary mb-2 font-medium">
              {q.label}
              {q.required && <span className="text-accent-red ml-1">*</span>}
            </p>
            {answered || !active ? (
              <p className="text-sm text-accent-blue">
                {answered && answered[q.id] !== undefined
                  ? Array.isArray(answered[q.id])
                    ? (answered[q.id] as string[]).join(', ')
                    : String(answered[q.id])
                  : <span className="text-content-muted">(응답 없음)</span>}
              </p>
            ) : q.type === 'text' ? (
              <textarea
                rows={2}
                placeholder={q.placeholder}
                value={(values[q.id] as string) ?? ''}
                onChange={(e) => setValues((s) => ({ ...s, [q.id]: e.target.value }))}
                className="w-full px-3 py-2 bg-surface-primary border border-border rounded-md text-sm text-content-primary placeholder-content-muted focus:outline-none focus:border-accent-primary transition-colors"
              />
            ) : (
              <div className="space-y-2">
                {q.options!.map((opt) => (
                  <label key={opt} className="flex items-center gap-2 text-sm text-content-primary cursor-pointer hover:text-accent-primary transition-colors">
                    <input
                      type={q.type === 'single_choice' ? 'radio' : 'checkbox'}
                      name={q.id}
                      checked={
                        q.type === 'single_choice'
                          ? values[q.id] === opt && !others[q.id]
                          : ((values[q.id] as string[]) ?? []).includes(opt)
                      }
                      onChange={() => {
                        if (q.type === 'single_choice') {
                          setValues((s) => ({ ...s, [q.id]: opt }))
                          setOthers((s) => ({ ...s, [q.id]: '' }))
                        } else toggle(q.id, opt)
                      }}
                      className="accent-accent-primary"
                    />
                    {opt}
                  </label>
                ))}
                {q.allow_other && (
                  <input
                    placeholder="기타 (직접 입력)"
                    value={others[q.id] ?? ''}
                    onChange={(e) => setOthers((s) => ({ ...s, [q.id]: e.target.value }))}
                    className="w-full mt-1 px-3 py-2 bg-surface-primary border border-border rounded-md text-sm text-content-primary placeholder-content-muted focus:outline-none focus:border-accent-primary transition-colors"
                  />
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {active && (
        <div className="mt-4 flex items-center gap-2 pt-3 border-t border-border">
          <button
            disabled={busy}
            onClick={() => submit(false)}
            className="px-4 py-2 bg-accent-primary hover:bg-accent-primary/90 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-md text-sm font-medium transition-colors"
          >
            제출
          </button>
          <button
            disabled={busy}
            onClick={() => submit(true)}
            className="px-4 py-2 bg-surface-tertiary hover:bg-surface-hover disabled:opacity-50 disabled:cursor-not-allowed text-content-secondary rounded-md text-sm font-medium transition-colors"
          >
            취소
          </button>
          {error && <span className="text-xs text-accent-red ml-2">{error}</span>}
        </div>
      )}
      {sent && form.state === 'pending' && (
        <p className="mt-3 text-xs text-content-secondary bg-surface-tertiary px-3 py-2 rounded-md">
          ✓ 응답을 전달했습니다. 작업을 이어갑니다...
        </p>
      )}
      {form.state === 'cancelled' && (
        <p className="mt-3 text-xs text-content-muted bg-surface-tertiary px-3 py-2 rounded-md">
          ✗ 질문을 취소했습니다.
        </p>
      )}
      {form.state === 'timeout' && (
        <p className="mt-3 text-xs text-accent-orange bg-surface-tertiary px-3 py-2 rounded-md">
          ⚠ 응답 시간이 초과되었습니다.
        </p>
      )}
      {form.state === 'pending' && !interactive && !sent && (
        <p className="mt-3 text-xs text-content-muted bg-surface-tertiary px-3 py-2 rounded-md">
          ⓘ 이 질문은 더 이상 응답할 수 없습니다.
        </p>
      )}
    </div>
  )
}

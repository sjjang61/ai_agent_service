import { ArrowDown, ArrowUp, Plus, X } from 'lucide-react'
import type { SiteSpec, VerticalSpec } from '../../api/siteProfiles'
import { siteSpecOf, verticalSpecOf } from '../../api/siteProfiles'
import { inputCls } from '../skills/common'

const cell = `${inputCls} !py-1.5 !text-[13px]`

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-1.5">
      <div>
        <h3 className="text-[13px] font-semibold text-content-primary">{title}</h3>
        {hint && <p className="text-xs text-content-tertiary">{hint}</p>}
      </div>
      {children}
    </section>
  )
}

/** 행을 더하고 지우고 옮기는 목록. render 가 한 행의 입력칸들을 그린다. */
function Rows<T>({ items, onChange, blank, addLabel, movable = true, render }: {
  items: T[]
  onChange: (next: T[]) => void
  blank: () => T
  addLabel: string
  movable?: boolean
  render: (item: T, patch: (p: Partial<T>) => void) => React.ReactNode
}) {
  const move = (i: number, d: number) => {
    const next = [...items]
    ;[next[i], next[i + d]] = [next[i + d], next[i]]
    onChange(next)
  }
  return (
    <div className="space-y-1.5">
      {items.map((it, i) => (
        <div key={i} className="flex gap-1.5 items-start">
          <div className="flex-1 min-w-0 grid gap-1.5">{render(it, (p) => onChange(items.map((x, j) => (j === i ? { ...x, ...p } : x))))}</div>
          <div className="flex flex-col flex-shrink-0">
            {movable && (
              <>
                <button type="button" aria-label="위로" disabled={i === 0} onClick={() => move(i, -1)} className="p-0.5 border-none bg-transparent text-content-muted hover:text-content-primary disabled:opacity-30 cursor-pointer"><ArrowUp size={13} /></button>
                <button type="button" aria-label="아래로" disabled={i === items.length - 1} onClick={() => move(i, 1)} className="p-0.5 border-none bg-transparent text-content-muted hover:text-content-primary disabled:opacity-30 cursor-pointer"><ArrowDown size={13} /></button>
              </>
            )}
            <button type="button" aria-label="삭제" onClick={() => onChange(items.filter((_, j) => j !== i))} className="p-0.5 border-none bg-transparent text-content-muted hover:text-accent-red cursor-pointer"><X size={13} /></button>
          </div>
        </div>
      ))}
      <button type="button" onClick={() => onChange([...items, blank()])} className="inline-flex items-center gap-1 text-[13px] text-accent-primary border-none bg-transparent cursor-pointer p-0">
        <Plus size={13} /> {addLabel}
      </button>
    </div>
  )
}

const KEY_HINT = '영문 소문자·숫자·밑줄'

/** 분야의 구조: 이 분야 작업에 필요한 입력값, 표준 진행 단계, 재현 검증에 쓸 샘플 값. */
export function VerticalSpecEditor({ value, onChange }: { value: Partial<VerticalSpec> | undefined; onChange: (v: VerticalSpec) => void }) {
  const spec = verticalSpecOf(value)
  const set = (p: Partial<VerticalSpec>) => onChange({ ...spec, ...p })
  return (
    <div className="space-y-4 p-3 border border-border rounded-[var(--radius-lg)]">
      <Section title="입력값" hint="이 분야의 작업을 하려면 어떤 값이 필요한가. 사이트마다 이 값을 넣는 방법을 따로 적고, 재현 검증은 샘플 값으로 수행합니다. 한 항목은 두 줄입니다: ① 키 · 이름 · 필수 여부 ② 형식 · 예시 · 검증용 샘플 값.">
        <Rows
          items={spec.inputs}
          onChange={(inputs) => set({ inputs })}
          blank={() => ({ key: '', label: '', required: true, format: '', example: '' })}
          addLabel="입력값 추가"
          render={(it, patch) => (
            <>
              <div className="grid grid-cols-[110px_1fr_auto] gap-1.5 items-center">
                <input value={it.key} onChange={(e) => patch({ key: e.target.value })} placeholder="키" title={KEY_HINT} className={`${cell} font-mono`} />
                <input value={it.label} onChange={(e) => patch({ label: e.target.value })} placeholder="이름 (예: 출발지)" className={cell} />
                <label className="flex items-center gap-1 text-xs text-content-secondary whitespace-nowrap"><input type="checkbox" checked={it.required} onChange={(e) => patch({ required: e.target.checked })} />필수</label>
              </div>
              <div className="grid grid-cols-[1fr_150px_150px] gap-1.5">
                <input value={it.format} onChange={(e) => patch({ format: e.target.value })} placeholder="형식 (예: 도시명 또는 공항 코드)" className={cell} />
                <input value={it.example} onChange={(e) => patch({ example: e.target.value })} placeholder="예시" className={cell} />
                <input value={spec.sample[it.key] ?? ''} onChange={(e) => set({ sample: { ...spec.sample, [it.key]: e.target.value } })} placeholder="검증용 샘플 값" title="재현 검증에서 이 값을 씁니다" className={cell} />
              </div>
            </>
          )}
        />
      </Section>
      <Section title="표준 진행 단계" hint="사이트와 상관없이 이 분야의 작업이 거치는 순서. 상태를 바꾸는 단계(장바구니·좌석·예약)는 ‘실행 안 함’으로 표시하면 분석·검증에서 시험하지 않습니다.">
        <Rows
          items={spec.flow}
          onChange={(flow) => set({ flow })}
          blank={() => ({ key: '', title: '', desc: '', write: false })}
          addLabel="단계 추가"
          render={(it, patch) => (
            <>
              <div className="grid grid-cols-[110px_1fr_auto] gap-1.5 items-center">
                <input value={it.key} onChange={(e) => patch({ key: e.target.value })} placeholder="키" title={KEY_HINT} className={`${cell} font-mono`} />
                <input value={it.title} onChange={(e) => patch({ title: e.target.value })} placeholder="단계 이름 (예: 조건 입력·검색)" className={cell} />
                <label className="flex items-center gap-1 text-xs text-content-secondary whitespace-nowrap"><input type="checkbox" checked={it.write} onChange={(e) => patch({ write: e.target.checked })} />실행 안 함(상태 변경)</label>
              </div>
              <input value={it.desc} onChange={(e) => patch({ desc: e.target.value })} placeholder="설명 (이 단계에서 할 일, 확인할 것)" className={cell} />
            </>
          )}
        />
      </Section>
    </div>
  )
}

/** 사이트의 구조: 진입 주소, 메뉴 지도, 입력값별 입력 방법, 단계별 동작, 멈출 지점. 입력값·단계는 분야의 정의를 따른다. */
export function SiteSpecEditor({ value, vertical, onChange }: { value: Partial<SiteSpec> | undefined; vertical: Partial<VerticalSpec> | undefined; onChange: (v: SiteSpec) => void }) {
  const spec = siteSpecOf(value)
  const vspec = verticalSpecOf(vertical)
  const set = (p: Partial<SiteSpec>) => onChange({ ...spec, ...p })
  // 분야가 정의한 입력값·단계를 먼저, 분야에 없는(분야를 바꿨거나 직접 적은) 것은 아래에 남겨 지워지지 않게 한다
  const inputKeys = [...vspec.inputs.map((i) => i.key), ...Object.keys(spec.inputs).filter((k) => !vspec.inputs.some((i) => i.key === k))]
  const flowKeys = [...vspec.flow.map((s) => s.key), ...spec.flow.map((s) => s.key).filter((k) => !vspec.flow.some((s) => s.key === k))]
  const inputLabel = (k: string) => vspec.inputs.find((i) => i.key === k)?.label ?? `${k} (분야에 없음)`
  const flowTitle = (k: string) => vspec.flow.find((s) => s.key === k)?.title ?? `${k} (분야에 없음)`
  const setInput = (k: string, p: Partial<{ how: string; param: string }>) => set({ inputs: { ...spec.inputs, [k]: { how: spec.inputs[k]?.how ?? '', param: spec.inputs[k]?.param ?? '', ...p } } })
  const setFlow = (k: string, p: Partial<{ how: string; url: string; skip: boolean }>) => {
    const cur = spec.flow.find((s) => s.key === k)
    set({ flow: cur ? spec.flow.map((s) => (s.key === k ? { ...s, ...p } : s)) : [...spec.flow, { key: k, how: '', url: '', ...p }] })
  }
  return (
    <div className="space-y-4 p-3 border border-border rounded-[var(--radius-lg)]">
      <Section title="진입·직접 이동 주소" hint="조건을 주소로 넣을 수 있으면 그 주소를 적으세요. 입력값 자리는 {키} 로 씁니다 (예: https://…/search?query={query}).">
        <Rows
          items={spec.entry}
          onChange={(entry) => set({ entry })}
          blank={() => ({ label: '', url: '' })}
          addLabel="주소 추가"
          render={(it, patch) => (
            <div className="grid grid-cols-[130px_1fr] gap-1.5">
              <input value={it.label} onChange={(e) => patch({ label: e.target.value })} placeholder="이름 (예: 검색 결과)" className={cell} />
              <input value={it.url} onChange={(e) => patch({ url: e.target.value })} placeholder="https://" className={`${cell} font-mono`} />
            </div>
          )}
        />
      </Section>
      <Section title="메뉴·화면 지도" hint="이 분야 작업에 쓰는 메뉴가 어디에 있고 어디로 이어지는가.">
        <Rows
          items={spec.menus}
          onChange={(menus) => set({ menus })}
          blank={() => ({ name: '', path: '', url: '' })}
          addLabel="메뉴 추가"
          render={(it, patch) => (
            <div className="grid grid-cols-[110px_1fr_1fr] gap-1.5">
              <input value={it.name} onChange={(e) => patch({ name: e.target.value })} placeholder="메뉴 이름" className={cell} />
              <input value={it.path} onChange={(e) => patch({ path: e.target.value })} placeholder="위치 (예: 상단 메뉴 > 항공권)" className={cell} />
              <input value={it.url} onChange={(e) => patch({ url: e.target.value })} placeholder="이동 주소 (선택)" className={`${cell} font-mono`} />
            </div>
          )}
        />
      </Section>
      <Section title="입력값 넣는 방법" hint={vspec.inputs.length ? '분야가 정의한 입력값마다, 이 사이트에서 어떻게 넣는지 (주소 파라미터·입력창·자동완성·달력).' : '분야를 고르면 그 분야의 입력값이 여기에 나옵니다.'}>
        <div className="space-y-1.5">
          {inputKeys.map((k) => (
            <div key={k} className="grid grid-cols-[110px_1fr_110px] gap-1.5 items-center">
              <span className="text-[12.5px] text-content-primary truncate" title={k}>{inputLabel(k)}</span>
              <input value={spec.inputs[k]?.how ?? ''} onChange={(e) => setInput(k, { how: e.target.value })} placeholder="넣는 방법" className={cell} />
              <input value={spec.inputs[k]?.param ?? ''} onChange={(e) => setInput(k, { param: e.target.value })} placeholder="주소 파라미터" className={`${cell} font-mono`} />
            </div>
          ))}
        </div>
      </Section>
      <Section title="단계별 이 사이트에서의 동작" hint={vspec.flow.length ? '분야의 표준 단계를 이 사이트에서 어떻게 수행하는가. 사람 확인(CAPTCHA) 때문에 할 수 없는 단계는 "하지 않음"으로 표시하고 사유와 대안을 적으세요.' : '분야를 고르면 그 분야의 표준 단계가 여기에 나옵니다.'}>
        <div className="space-y-1.5">
          {flowKeys.map((k) => (
            <div key={k} className="space-y-1">
              <div className="grid grid-cols-[110px_1fr_1fr] gap-1.5 items-center">
                <span className="text-[12.5px] text-content-primary truncate" title={k}>{flowTitle(k)}</span>
                <input value={spec.flow.find((s) => s.key === k)?.how ?? ''} onChange={(e) => setFlow(k, { how: e.target.value })} placeholder={spec.flow.find((s) => s.key === k)?.skip ? '하지 않는 사유와 대신 할 일' : '수행 방법'} className={cell} />
                <input value={spec.flow.find((s) => s.key === k)?.url ?? ''} onChange={(e) => setFlow(k, { url: e.target.value })} placeholder="주소 (선택)" className={`${cell} font-mono`} />
              </div>
              <label className="flex items-center gap-1.5 pl-[116px] text-xs text-content-secondary cursor-pointer" title="보안 확인(CAPTCHA)처럼 이 사이트에서는 할 수 없는 단계. 에이전트는 이 단계를 하지 않고 적어 둔 대안을 따르며, 재현 검증도 이 단계를 감점하지 않습니다.">
                <input type="checkbox" checked={!!spec.flow.find((s) => s.key === k)?.skip} onChange={(e) => setFlow(k, { skip: e.target.checked })} />
                이 사이트에서는 하지 않음
              </label>
            </div>
          ))}
        </div>
      </Section>
      <Section title="멈출 지점" hint="결제·예약 직전에 멈출 화면의 이름과 주소.">
        <input value={spec.stop_point} onChange={(e) => set({ stop_point: e.target.value })} placeholder="예: 예약자 정보 입력 화면 (…/booking/passenger)" className={cell} />
      </Section>
    </div>
  )
}

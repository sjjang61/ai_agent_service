import { useState } from 'react'
import { ChevronDown, Plus, Trash2 } from 'lucide-react'
import { inputCls } from '../skills/common'
import type { AgentConfig, Catalog, CatalogTool, SubAgent, ValidationIssue } from '../../types/customAgent'

export type TabKey = 'basic' | 'prompt' | 'tools' | 'skills' | 'mcp' | 'team' | 'advanced'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'basic', label: '기본' },
  { key: 'prompt', label: '지침' },
  { key: 'tools', label: '도구' },
  { key: 'skills', label: '스킬' },
  { key: 'mcp', label: 'MCP' },
  { key: 'team', label: '서브에이전트' },
  { key: 'advanced', label: '모델·제한' },
]

const RISK: Record<CatalogTool['risk'], { label: string; cls: string }> = {
  read: { label: '읽기', cls: 'bg-accent-green/15 text-accent-green' },
  write: { label: '변경', cls: 'bg-accent-amber/15 text-accent-amber' },
  exec: { label: '실행', cls: 'bg-accent-red/15 text-accent-red' },
}

const label = 'block text-[13px] font-medium text-content-primary'
const hint = 'text-xs text-content-tertiary'

function Radio<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: { v: T; label: string; hint?: string }[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => (
        <button
          key={o.v}
          type="button"
          onClick={() => onChange(o.v)}
          title={o.hint}
          className={`px-3.5 py-1.5 rounded-full text-[13px] border cursor-pointer transition-colors ${
            value === o.v ? 'border-accent-primary bg-accent-primary/15 text-content-primary' : 'border-border bg-transparent text-content-secondary hover:bg-surface-hover'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

function Check({ checked, onChange, children }: { checked: boolean; onChange: (v: boolean) => void; children: React.ReactNode }) {
  return (
    <label className="flex items-start gap-2.5 cursor-pointer py-1">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="mt-1" />
      <span className="min-w-0">{children}</span>
    </label>
  )
}

function toggle(list: string[], name: string, on: boolean): string[] {
  return on ? (list.includes(name) ? list : [...list, name]) : list.filter((x) => x !== name)
}

interface Props {
  name: string
  description: string
  icon: string
  config: AgentConfig
  catalog: Catalog | undefined
  issues: ValidationIssue[]
  onMeta: (m: { name?: string; description?: string; icon?: string }) => void
  onConfig: (c: AgentConfig) => void
}

export default function BuilderForm({ name, description, icon, config, catalog, issues, onMeta, onConfig }: Props) {
  const [tab, setTab] = useState<TabKey>('basic')
  const set = <K extends keyof AgentConfig>(k: K, v: AgentConfig[K]) => onConfig({ ...config, [k]: v })
  const tools = catalog?.tools ?? []
  const groups = [...new Set(tools.map((t) => t.group))]
  const issueCount = (prefix: string) => issues.filter((i) => i.path.startsWith(prefix)).length
  const badge: Record<TabKey, number> = {
    basic: 0,
    prompt: issueCount('prompt'),
    tools: issueCount('tools'),
    skills: issueCount('skills'),
    mcp: issueCount('mcp'),
    team: issueCount('team'),
    advanced: issueCount('model'),
  }
  const memberToolPool = config.tools.mode === 'selected' ? tools.filter((t) => config.tools.allow.includes(t.name)) : tools

  const updateMember = (i: number, patch: Partial<SubAgent>) =>
    set('team', { ...config.team, members: config.team.members.map((m, j) => (j === i ? { ...m, ...patch } : m)) })

  return (
    <div className="flex flex-col min-h-0 h-full">
      <div className="flex gap-1 border-b border-border px-1 flex-shrink-0 overflow-x-auto" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`relative px-3.5 py-2.5 text-[13px] whitespace-nowrap border-none bg-transparent cursor-pointer border-b-2 -mb-px ${
              tab === t.key ? 'text-content-primary border-b-accent-primary' : 'text-content-tertiary hover:text-content-primary border-b-transparent'
            }`}
            style={{ borderBottomWidth: 2, borderBottomStyle: 'solid', borderBottomColor: tab === t.key ? 'var(--accent-primary)' : 'transparent' }}
          >
            {t.label}
            {badge[t.key] > 0 && <span className="ml-1 inline-block w-1.5 h-1.5 rounded-full bg-accent-amber align-middle" />}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {tab === 'basic' && (
          <>
            <div className="grid grid-cols-[72px_1fr] gap-3">
              <div className="space-y-1.5">
                <label className={label} htmlFor="agent-icon">아이콘</label>
                <input id="agent-icon" value={icon} onChange={(e) => onMeta({ icon: e.target.value.slice(0, 4) })} className={`${inputCls} text-center text-lg`} />
              </div>
              <div className="space-y-1.5">
                <label className={label} htmlFor="agent-name">이름</label>
                <input id="agent-name" value={name} onChange={(e) => onMeta({ name: e.target.value })} maxLength={100} className={inputCls} />
              </div>
            </div>
            <div className="space-y-1.5">
              <label className={label} htmlFor="agent-desc">설명</label>
              <input id="agent-desc" value={description} onChange={(e) => onMeta({ description: e.target.value })} maxLength={500} placeholder="이 에이전트가 무엇을 하는지 한 줄로" className={inputCls} />
            </div>
            <div className="space-y-2">
              <label className={label}>시작 질문 (최대 4개)</label>
              {config.prompt.starters.map((s, i) => (
                <div key={i} className="flex gap-2">
                  <input
                    value={s}
                    onChange={(e) => set('prompt', { ...config.prompt, starters: config.prompt.starters.map((x, j) => (j === i ? e.target.value : x)) })}
                    maxLength={200}
                    className={inputCls}
                  />
                  <button onClick={() => set('prompt', { ...config.prompt, starters: config.prompt.starters.filter((_, j) => j !== i) })} aria-label="삭제" className="text-content-muted hover:text-accent-red border-none bg-transparent cursor-pointer"><Trash2 size={15} /></button>
                </div>
              ))}
              {config.prompt.starters.length < 4 && (
                <button onClick={() => set('prompt', { ...config.prompt, starters: [...config.prompt.starters, ''] })} className="flex items-center gap-1 text-[13px] text-accent-primary border-none bg-transparent cursor-pointer">
                  <Plus size={14} /> 질문 추가
                </button>
              )}
            </div>
          </>
        )}

        {tab === 'prompt' && (
          <div className="space-y-2">
            <label className={label} htmlFor="agent-instructions">지침 (역할·말투·절차)</label>
            <textarea
              id="agent-instructions"
              value={config.prompt.instructions}
              onChange={(e) => set('prompt', { ...config.prompt, instructions: e.target.value })}
              rows={16}
              maxLength={20000}
              placeholder={'예)\n당신은 …를 돕는 에이전트입니다.\n- 답변은 결론부터 쓴다\n- 모르는 것은 추측하지 않는다'}
              className={`${inputCls} font-mono resize-y`}
            />
            <p className={hint}>
              기본 시스템 프롬프트(응답 범위 원칙, 도구 사용 규칙) 뒤에 덧붙여집니다. {config.prompt.instructions.length.toLocaleString()} / 20,000자 · 비밀번호나 API 키는 적지 마세요.
            </p>
          </div>
        )}

        {tab === 'tools' && (
          <>
            <div className="space-y-2">
              <Radio
                value={config.tools.mode}
                onChange={(v) => set('tools', { ...config.tools, mode: v })}
                options={[{ v: 'all', label: '기본 도구 전체' }, { v: 'selected', label: '선택한 도구만' }]}
              />
              <p className={hint}>스킬(load_skill)과 MCP 도구는 각각 스킬·MCP 탭에서 따로 정합니다.</p>
            </div>
            {config.tools.mode === 'selected' &&
              groups.map((g) => {
                const inGroup = tools.filter((t) => t.group === g)
                const allOn = inGroup.every((t) => config.tools.allow.includes(t.name))
                return (
                  <div key={g} className="rounded-[var(--radius-lg)] border border-border">
                    <div className="flex items-center justify-between px-4 py-2 bg-surface-secondary rounded-t-[var(--radius-lg)]">
                      <span className="text-[13px] font-medium text-content-primary">{g}</span>
                      <button
                        onClick={() =>
                          set('tools', {
                            ...config.tools,
                            allow: allOn
                              ? config.tools.allow.filter((n) => !inGroup.some((t) => t.name === n))
                              : [...new Set([...config.tools.allow, ...inGroup.map((t) => t.name)])],
                          })
                        }
                        className="text-xs text-accent-primary border-none bg-transparent cursor-pointer"
                      >
                        {allOn ? '모두 해제' : '모두 선택'}
                      </button>
                    </div>
                    <div className="px-4 py-1.5">
                      {inGroup.map((t) => (
                        <Check key={t.name} checked={config.tools.allow.includes(t.name)} onChange={(on) => set('tools', { ...config.tools, allow: toggle(config.tools.allow, t.name, on) })}>
                          <span className="flex items-center gap-2">
                            <span className="text-[13px] font-mono text-content-primary">{t.name}</span>
                            <span className={`text-[10px] px-1.5 py-0.5 rounded ${RISK[t.risk].cls}`}>{RISK[t.risk].label}</span>
                          </span>
                          <span className={`block ${hint}`}>{t.description}</span>
                        </Check>
                      ))}
                    </div>
                  </div>
                )
              })}
          </>
        )}

        {tab === 'skills' && (
          <>
            <Radio
              value={config.skills.mode}
              onChange={(v) => set('skills', { ...config.skills, mode: v })}
              options={[{ v: 'all', label: '설치된 스킬 전체' }, { v: 'selected', label: '선택한 스킬만' }, { v: 'none', label: '사용 안 함' }]}
            />
            {config.skills.mode === 'selected' && (
              <div className="rounded-[var(--radius-lg)] border border-border px-4 py-1.5">
                {(catalog?.skills ?? []).length === 0 && <p className={`${hint} py-2`}>설치된 스킬이 없습니다. 스킬 메뉴에서 설치하세요.</p>}
                {(catalog?.skills ?? []).map((s) => (
                  <Check key={s.name} checked={config.skills.names.includes(s.name)} onChange={(on) => set('skills', { ...config.skills, names: toggle(config.skills.names, s.name, on) })}>
                    <span className="text-[13px] text-content-primary">{s.name}{!s.is_active && <span className="ml-2 text-[10px] text-content-tertiary">(비활성)</span>}</span>
                    {s.description && <span className={`block ${hint} line-clamp-2`}>{s.description}</span>}
                  </Check>
                ))}
              </div>
            )}
          </>
        )}

        {tab === 'mcp' && (
          <>
            <Radio
              value={config.mcp.mode}
              onChange={(v) => set('mcp', { ...config.mcp, mode: v })}
              options={[{ v: 'all', label: '등록한 MCP 서버 전체' }, { v: 'selected', label: '선택한 서버만' }, { v: 'none', label: '사용 안 함' }]}
            />
            {config.mcp.mode === 'selected' && (
              <div className="space-y-2">
                {(catalog?.mcp_servers ?? []).length === 0 && <p className={hint}>등록된 MCP 서버가 없습니다. MCP 설정 메뉴에서 추가하세요.</p>}
                {(catalog?.mcp_servers ?? []).map((s) => {
                  const rule = config.mcp.servers.find((r) => r.name === s.name)
                  return (
                    <div key={s.name} className="rounded-[var(--radius-lg)] border border-border px-4 py-2">
                      <Check
                        checked={!!rule}
                        onChange={(on) => set('mcp', { ...config.mcp, servers: on ? [...config.mcp.servers, { name: s.name, allowed_tools: null }] : config.mcp.servers.filter((r) => r.name !== s.name) })}
                      >
                        <span className="text-[13px] text-content-primary">{s.display_name}</span>
                        <span className="ml-2 text-[10px] text-content-tertiary">{s.transport}</span>
                      </Check>
                      {rule && (
                        <div className="pl-6 pb-1">
                          {s.tools.length === 0 ? (
                            <p className={hint}>모든 도구를 허용합니다. (서버가 연결되면 도구별로 제한할 수 있습니다)</p>
                          ) : (
                            <>
                              <Check
                                checked={rule.allowed_tools === null}
                                onChange={(on) => set('mcp', { ...config.mcp, servers: config.mcp.servers.map((r) => (r.name === s.name ? { ...r, allowed_tools: on ? null : [...s.tools] } : r)) })}
                              >
                                <span className="text-[13px] text-content-secondary">모든 도구 허용 ({s.tools.length}개)</span>
                              </Check>
                              {rule.allowed_tools !== null &&
                                s.tools.map((t) => (
                                  <Check
                                    key={t}
                                    checked={rule.allowed_tools!.includes(t)}
                                    onChange={(on) => set('mcp', { ...config.mcp, servers: config.mcp.servers.map((r) => (r.name === s.name ? { ...r, allowed_tools: toggle(r.allowed_tools ?? [], t, on) } : r)) })}
                                  >
                                    <span className="text-[13px] font-mono text-content-primary">{t}</span>
                                  </Check>
                                ))}
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
            <p className={hint}>stdio MCP 서버는 서버에서 프로세스로 실행됩니다. 신뢰할 수 있는 서버만 연결하세요.</p>
          </>
        )}

        {tab === 'team' && (
          <>
            <Radio
              value={config.team.mode}
              onChange={(v) => set('team', { ...config.team, mode: v })}
              options={[
                { v: 'default', label: '기본 팀', hint: 'Research / Coder / Explorer 서브에이전트가 자동 구성됩니다' },
                { v: 'custom', label: '직접 구성', hint: '아래에서 만든 서브에이전트만 사용합니다' },
                { v: 'none', label: '서브에이전트 없음', hint: '이 에이전트가 직접 모든 일을 합니다' },
              ]}
            />
            <p className={hint}>
              {config.team.mode === 'default' && '필요하면 기본 서브에이전트(검색·코드·탐색)에게 작업을 위임합니다.'}
              {config.team.mode === 'none' && '위임 없이 허용된 도구를 직접 사용합니다. 단순하고 빠릅니다.'}
              {config.team.mode === 'custom' && '서브에이전트에 배정한 도구는 그 서브에이전트만 쓰고, 나머지 허용 도구는 이 에이전트가 직접 씁니다.'}
            </p>
            {config.team.mode === 'custom' && (
              <div className="space-y-3">
                {config.team.members.map((m, i) => (
                  <div key={i} className="rounded-[var(--radius-lg)] border border-border p-4 space-y-3">
                    <div className="flex gap-2">
                      <input value={m.name} onChange={(e) => updateMember(i, { name: e.target.value })} placeholder="이름 (영문/숫자/-/_)" maxLength={40} aria-label="서브에이전트 이름" className={inputCls} />
                      <button onClick={() => set('team', { ...config.team, members: config.team.members.filter((_, j) => j !== i) })} aria-label="서브에이전트 삭제" className="text-content-muted hover:text-accent-red border-none bg-transparent cursor-pointer"><Trash2 size={15} /></button>
                    </div>
                    <input value={m.role} onChange={(e) => updateMember(i, { role: e.target.value })} placeholder="역할 설명 (리더가 위임 대상을 고르는 기준)" maxLength={300} aria-label="역할" className={inputCls} />
                    <textarea value={m.instructions} onChange={(e) => updateMember(i, { instructions: e.target.value })} placeholder="이 서브에이전트의 지침 (선택)" rows={3} maxLength={4000} aria-label="지침" className={`${inputCls} resize-y`} />
                    <div>
                      <div className="text-xs text-content-tertiary mb-1">사용할 도구</div>
                      <div className="flex flex-wrap gap-x-4">
                        {memberToolPool.map((t) => (
                          <Check key={t.name} checked={m.tools.includes(t.name)} onChange={(on) => updateMember(i, { tools: toggle(m.tools, t.name, on) })}>
                            <span className="text-xs font-mono text-content-primary">{t.name}</span>
                          </Check>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
                {config.team.members.length < 6 && (
                  <button
                    onClick={() => set('team', { ...config.team, members: [...config.team.members, { name: `Agent${config.team.members.length + 1}`, role: '', instructions: '', tools: [] }] })}
                    className="flex items-center gap-1 text-[13px] text-accent-primary border-none bg-transparent cursor-pointer"
                  >
                    <Plus size={14} /> 서브에이전트 추가
                  </button>
                )}
              </div>
            )}
          </>
        )}

        {tab === 'advanced' && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className={label} htmlFor="agent-provider">LLM 종류</label>
                <div className="relative">
                  <select id="agent-provider" value={config.model.llm_provider ?? ''} onChange={(e) => set('model', { ...config.model, llm_provider: e.target.value || null })} className={`${inputCls} appearance-none pr-8`}>
                    <option value="">서버 기본값</option>
                    {(catalog?.llm_providers ?? []).map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                  <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-content-tertiary" />
                </div>
              </div>
              <div className="space-y-1.5">
                <label className={label} htmlFor="agent-model">모델</label>
                <input id="agent-model" value={config.model.model ?? ''} onChange={(e) => set('model', { ...config.model, model: e.target.value || null })} placeholder="비우면 기본 모델" className={inputCls} />
              </div>
            </div>
            <div className="space-y-1.5">
              <label className={label} htmlFor="agent-iter">최대 도구 호출 횟수 (1~50)</label>
              <input id="agent-iter" type="number" min={1} max={50} value={config.model.max_iterations ?? ''} onChange={(e) => set('model', { ...config.model, max_iterations: e.target.value ? Math.min(50, Math.max(1, Number(e.target.value))) : null })} placeholder="기본값" className={`${inputCls} max-w-[160px]`} />
            </div>
            <Check checked={config.memory.enabled} onChange={(on) => set('memory', { enabled: on })}>
              <span className="text-[13px] text-content-primary">내 메모리 사용</span>
              <span className={`block ${hint}`}>메모리는 에이전트가 아니라 사용자 것입니다. 켜면 내 메모리를 불러오고 대화에서 새 정보를 저장합니다. 끄면 이 에이전트는 메모리를 쓰지 않습니다.</span>
            </Check>
          </>
        )}
      </div>

      {issues.length > 0 && (
        <div className="border-t border-border px-5 py-3 max-h-36 overflow-y-auto space-y-1 flex-shrink-0" role="status">
          {issues.map((i, k) => (
            <div key={k} className={`text-xs flex gap-2 ${i.level === 'error' ? 'text-accent-red' : 'text-accent-amber'}`}>
              <span className="flex-shrink-0 font-medium">{i.level === 'error' ? '오류' : '주의'}</span>
              <span>{i.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

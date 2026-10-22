import type { AgentStep } from '../../types/agent'

/** 도구 이름 → 화면에 보여 줄 한글 이름 (StepProgressItem 과 같은 표) */
export const TASK_LABELS: Record<string, string> = {
  delegate_task_to_member: '팀원에게 위임',
  code_executor: '코드 실행',
  file_manager: '파일 관리',
  shell_executor: '쉘 실행',
  web_search: '웹 검색',
  web_crawler: '웹 크롤링',
  read_file: '파일 읽기',
  write_file: '파일 쓰기',
  edit_file: '파일 수정',
  grep_file: '파일 검색',
  delete_file: '파일 삭제',
  download_file: '파일 다운로드',
  publish_file: '링크 발행',
  exec_command: '명령 실행',
  read_image: '이미지 분석',
  create_widget: '위젯 생성',
  load_skill: '스킬 불러오기',
  register_skill: '스킬 설치',
  call_sub_agent: '서브에이전트',
  load_mcp_tool: 'MCP 도구 확인',
  call_mcp_tool: 'MCP 호출',
  run_mcp_code: 'MCP 코드 실행',
  todo: '작업 계획',
  narrate: '진행 안내',
  form_ask_user: '사용자 질문',
  cli_browser_agent: '브라우저 작업',
  manage_schedule: '예약 관리',
  search_documents: '문서 검색',
  search_wiki: '위키 검색',
  memory_tool: '메모리',
}

export type TaskStatus = 'running' | 'done' | 'failed'

/** 도구 호출(tool_call)과 그 결과(tool_result)를 하나로 묶은 한 줄 작업 */
export interface TaskItem {
  key: string
  kind: 'tool' | 'thought'
  tool?: string
  label: string
  summary: string
  status: TaskStatus
  call?: AgentStep
  result?: AgentStep
  /** 하위 작업. same: 같은 종류의 연속 작업을 합친 것(파일 단위 등), delegate: 팀원에게 위임한 작업이 안에서 한 일 */
  children?: TaskItem[]
  childKind?: 'same' | 'delegate'
}

const clip = (s: string, n = 90) => {
  const t = s.replace(/\s+/g, ' ').trim()
  return t.length > n ? t.slice(0, n) + '…' : t
}

/** 도구 입력에서 사람이 알아볼 한 줄 요약을 만든다 (예: 검색어, 파일 경로, 스킬 이름) */
export function summarizeInput(tool: string | undefined, input: unknown): string {
  if (!input || typeof input !== 'object') return typeof input === 'string' ? clip(input) : ''
  const o = input as Record<string, unknown>
  const str = (k: string) => (typeof o[k] === 'string' ? (o[k] as string) : '')
  switch (tool) {
    case 'web_search':
      return clip(str('query'))
    case 'web_crawler':
    case 'download_file':
      return clip(str('url'))
    case 'load_skill': {
      const file = str('file')
      return file && file !== 'SKILL.md' ? `${str('name')} · ${file}` : str('name')
    }
    case 'read_file':
    case 'write_file':
    case 'edit_file':
    case 'delete_file':
    case 'grep_file':
    case 'publish_file':
    case 'read_image':
      return clip(str('path') || str('pattern'))
    case 'exec_command':
      return clip(str('command'))
    case 'code_executor':
      return clip(str('code'))
    case 'narrate':
      return clip(str('message'))
    case 'delegate_task_to_member':
      return clip([str('member_id'), str('task')].filter(Boolean).join(' · '))
    case 'call_mcp_tool':
      return clip([str('server'), str('tool')].filter(Boolean).join(' · '))
    case 'load_mcp_tool':
      return clip([str('server'), str('tool')].filter(Boolean).join(' · '))
    case 'create_widget':
      return clip(str('title'))
    default: {
      const first = Object.values(o).find((v) => typeof v === 'string' && v.trim()) as string | undefined
      return clip(first ?? JSON.stringify(o))
    }
  }
}

/** 연속해서 여러 번 호출되면 한 줄로 합쳐 보여 줄 도구 (예: 스킬 파일 4개를 차례로 읽기) */
const GROUPABLE = new Set([
  'read_file', 'grep_file', 'write_file', 'edit_file', 'delete_file',
  'web_search', 'web_crawler', 'download_file', 'read_image', 'load_skill', 'search_documents',
])

const UNIT: Record<string, string> = {
  read_file: '파일', grep_file: '검색', write_file: '파일', edit_file: '파일', delete_file: '파일',
  web_search: '검색', web_crawler: '페이지', download_file: '파일', read_image: '이미지',
  load_skill: '스킬 파일', search_documents: '검색',
}

const base = (s: string) => s.split('/').filter(Boolean).pop() ?? s

/** 연속된 같은 도구 작업(2개 이상)을 하나로 합친다. 합친 줄의 상태는 하나라도 진행 중이면 진행 중, 실패가 있으면 실패. */
export function groupTaskItems(items: TaskItem[]): TaskItem[] {
  const out: TaskItem[] = []
  let run: TaskItem[] = []
  const flush = () => {
    if (run.length < 2) out.push(...run)
    else {
      const first = run[0]
      const running = run.find((i) => i.status === 'running')
      const names = run.map((i) => base(i.summary.split(' · ').pop() ?? '')).filter(Boolean)
      const shown = names.slice(0, 3).join(', ')
      out.push({
        key: `group-${first.key}`,
        kind: 'tool',
        tool: first.tool,
        label: first.label,
        summary: running ? running.summary : `${shown}${names.length > 3 ? ` 외 ${names.length - 3}개` : ''}`,
        status: running ? 'running' : run.some((i) => i.status === 'failed') ? 'failed' : 'done',
        children: run,
        childKind: 'same',
      })
    }
    run = []
  }
  for (const it of items) {
    if (it.kind === 'tool' && it.tool && GROUPABLE.has(it.tool) && run.length && run[0].tool === it.tool) run.push(it)
    else {
      flush()
      if (it.kind === 'tool' && it.tool && GROUPABLE.has(it.tool)) run = [it]
      else out.push(it)
    }
  }
  flush()
  return out
}

export const groupUnit = (tool: string | undefined) => UNIT[tool ?? ''] ?? '건'

const EXEC_TOOLS = new Set(['exec_command', 'shell_executor'])

/** 명령어에서 무엇을 하려는지 추정한다. 모델이 purpose 를 비웠을 때의 보조 수단. */
export function describeCommand(command: string): string | null {
  const c = command.replace(/\s+/g, ' ').trim()
  let m: RegExpMatchArray | null
  if ((m = c.match(/\bnpx\b.*?\binstruct\s+([\w@./-]+)/))) return `스킬 지침 조회 (${m[1]})`
  if ((m = c.match(/\bnpx\b.*?\bfiles\s+([\w@./-]+)/))) return `스킬 파일 목록 조회 (${m[1]})`
  if (/\bnpx\b.*?\bupdate\b/.test(c)) return '패키지 업데이트 확인'
  if ((m = c.match(/\bnpm\s+(?:install|i)\s+(?:-\S+\s+)*([^\s-][^\s]*)/))) return `패키지 설치 (${m[1]})`
  if ((m = c.match(/\bnpm\s+(?:view|info)\s+([^\s]+)/))) return `패키지 정보 조회 (${m[1]})`
  if (/\bnpm\s+search\b/.test(c)) return '패키지 검색'
  if (/\bnpm\s+(?:test|run\s+build)\b|\bpytest\b|\btsc\b/.test(c)) return '빌드·테스트 실행'
  if (/\bpip3?\s+install\b/.test(c)) return 'Python 패키지 설치'
  if (/(^|[\s;&|])python3?\b/.test(c)) return 'Python 스크립트 실행'
  if (/(^|[\s;&|=)])node\b/.test(c)) return 'Node 스크립트 실행'
  if (/\bgit\s+clone\b/.test(c)) return '저장소 복제'
  if (/\b(?:curl|wget)\b/.test(c)) return '웹 요청·다운로드'
  if (/\b(?:soffice|libreoffice|pandoc)\b/.test(c)) return '문서 변환'
  if (/\b(?:unzip|tar|gunzip)\b/.test(c)) return '압축 해제'
  if (/\b(?:grep|rg|awk|sed)\b/.test(c)) return '내용 검색·추출'
  if (/\b(?:ls|find|tree)\b/.test(c)) return '파일 목록 확인'
  if (/\b(?:cat|head|tail)\b/.test(c)) return '파일 내용 확인'
  if (/\b(?:mkdir|cp|mv|rm|touch)\b/.test(c)) return '파일 정리'
  return null
}

/** 작업 이름: 모델이 적은 목적(purpose)이 있으면 그것, 없으면 명령에서 추정, 그것도 없으면 도구 기본 이름 */
function labelFor(tool: string | undefined, input: unknown): string {
  const base = TASK_LABELS[tool ?? ''] ?? tool ?? '도구'
  if (!input || typeof input !== 'object') return base
  const o = input as Record<string, unknown>
  if (typeof o.purpose === 'string' && o.purpose.trim()) return clip(o.purpose, 40)
  if (EXEC_TOOLS.has(tool ?? '') && typeof o.command === 'string') return describeCommand(o.command) ?? base
  if (tool === 'code_executor') return 'Python 코드 실행'
  return base
}

const FAILED = /^\s*(error\b|\[tool error\]|\[mcp error\]|traceback)/i

/**
 * 단계 목록(호출·결과가 따로 나열됨)을 '작업' 목록으로 묶는다.
 * 호출과 결과는 도구 이름이 같은 가장 최근의 미완료 호출과 짝짓는다 (findPendingCall 과 같은 규칙).
 * 결과가 아직 없으면 running, 결과가 오류로 시작하면 failed, 그 밖에는 done. 분석(thought)은 그 자체로 done.
 */
export function buildTaskItems(steps: AgentStep[]): TaskItem[] {
  return groupTaskItems(nestDelegates(buildFlatItems(steps)))
}

function buildFlatItems(steps: AgentStep[]): TaskItem[] {
  const items: TaskItem[] = []
  const pending: TaskItem[] = []
  for (const s of steps) {
    if (s.type === 'tool_call') {
      const item: TaskItem = {
        key: s.id,
        kind: 'tool',
        tool: s.tool,
        label: labelFor(s.tool, s.input),
        summary: summarizeInput(s.tool, s.input),
        status: 'running',
        call: s,
      }
      items.push(item)
      pending.push(item)
    } else if (s.type === 'tool_result') {
      let idx = -1
      // call_id 가 있으면 정확히 짝짓고 (같은 도구가 동시에 여러 번 돌 수 있다), 없으면 같은 도구의 가장 최근 호출과 짝짓는다
      if (s.callId) idx = pending.findIndex((p) => p.call?.callId === s.callId)
      if (idx < 0) {
        for (let i = pending.length - 1; i >= 0; i--) {
          if (pending[i].tool === s.tool && !(s.callId && pending[i].call?.callId)) {
            idx = i
            break
          }
        }
      }
      if (idx >= 0) {
        const [item] = pending.splice(idx, 1)
        item.result = s
        item.status = FAILED.test(s.output ?? '') ? 'failed' : 'done'
      } else {
        // 호출 없이 결과만 온 경우(저장된 일부 이력 등)도 한 줄로 보여 준다
        items.push({
          key: s.id,
          kind: 'tool',
          tool: s.tool,
          label: TASK_LABELS[s.tool ?? ''] ?? s.tool ?? '도구',
          summary: clip(s.output ?? ''),
          status: FAILED.test(s.output ?? '') ? 'failed' : 'done',
          result: s,
        })
      }
    } else if (s.type === 'thought') {
      items.push({ key: s.id, kind: 'thought', label: '분석', summary: clip(s.content ?? ''), status: 'done', call: s })
    }
  }
  return items
}

const key = (s: string) => s.toLowerCase().replace(/[^a-z0-9가-힣]/g, '')

/**
 * 팀원이 한 도구 호출(agent 가 붙은 호출)을 그 팀원에게 위임한 작업(delegate_task_to_member) 아래로 옮긴다.
 * 팀원 이름은 위임 입력의 member_id 와 대소문자·기호를 무시하고 맞춘다. 맞는 위임이 없으면 진행 중인 위임에 붙이고, 그것도 없으면 그대로 둔다.
 */
function nestDelegates(items: TaskItem[]): TaskItem[] {
  const top: TaskItem[] = []
  const delegates: TaskItem[] = []
  for (const it of items) {
    const agent = it.call?.agent ?? it.result?.agent
    if (agent && it.tool !== 'delegate_task_to_member' && delegates.length) {
      const same = delegates.filter((d) => key(String((d.call?.input as { member_id?: unknown } | undefined)?.member_id ?? '')) === key(agent))
      const parent =
        [...same].reverse().find((d) => d.status === 'running') ??
        same[same.length - 1] ??
        [...delegates].reverse().find((d) => d.status === 'running')
      if (parent) {
        ;(parent.children ??= []).push(it)
        continue
      }
    }
    top.push(it)
    if (it.tool === 'delegate_task_to_member') delegates.push(it)
  }
  for (const d of delegates) {
    if (!d.children) continue
    d.children = groupTaskItems(d.children)
    d.childKind = 'delegate'
    // 안의 작업이 아직 돌고 있으면 위임도 진행 중
    if (d.status === 'done' && d.children.some((c) => c.status === 'running')) d.status = 'running'
  }
  return top
}

/** 지금 진행 중인 가장 안쪽(마지막) 작업 */
export function currentTask(items: TaskItem[]): TaskItem | null {
  for (let i = items.length - 1; i >= 0; i--) {
    const it = items[i]
    if (it.children) {
      const inner = currentTask(it.children)
      if (inner) return inner
    }
    if (it.status === 'running') return it
  }
  return null
}

/** 각 단계(step) 시점에 '진행 중이던 계획 단계 id'. 계획이 만들어지기 전이면 null. todo 결과가 올 때마다 갱신한다. */
function activePlanStepAt(steps: AgentStep[]): (string | null)[] {
  let cur: string | null = null
  return steps.map((s) => {
    const at = cur
    if (s.type === 'tool_result' && s.tool === 'todo' && typeof s.output === 'string') {
      try {
        const p = JSON.parse(s.output)
        if (p?.ok && Array.isArray(p.todos) && p.todos.length) {
          const act = p.todos.find((t: { status: string }) => t.status === 'in_progress')
          if (act) cur = String(act.id)
          else if (p.todos.every((t: { status: string }) => t.status === 'completed')) cur = String(p.todos[p.todos.length - 1].id)
        }
      } catch {
        // 오류 문장은 무시
      }
    }
    return at
  })
}

export interface PlanBuckets {
  /** 계획이 만들어지기 전(또는 어느 단계에도 속하지 않는)에 한 작업 */
  pre: TaskItem[]
  /** 계획 단계 id → 그 단계가 진행 중일 때 한 작업 */
  byStep: Record<string, TaskItem[]>
}

/**
 * 작업 계획이 있을 때, 각 작업을 '그 작업을 할 때 진행 중이던 계획 단계' 아래로 나눈다.
 * 호출·결과 짝짓기와 팀원 위임 묶음은 전체 기준으로 먼저 하고, 같은 도구 연속 묶음은 단계 안에서만 한다.
 * todo 호출 자체는 계획 목록이 대신 보여 주므로 뺀다.
 */
export function buildPlanBuckets(steps: AgentStep[], planIds: string[]): PlanBuckets {
  const active = activePlanStepAt(steps)
  const indexOf = new Map(steps.map((s, i) => [s.id, i]))
  const known = new Set(planIds)
  const buckets: Record<string, TaskItem[]> = {}
  const pre: TaskItem[] = []
  for (const it of nestDelegates(buildFlatItems(steps))) {
    if (it.tool === 'todo') continue
    const at = indexOf.get((it.call ?? it.result)?.id ?? '')
    const id = at === undefined ? null : active[at]
    if (id && known.has(id)) (buckets[id] ??= []).push(it)
    else pre.push(it)
  }
  const byStep: Record<string, TaskItem[]> = {}
  for (const [id, list] of Object.entries(buckets)) byStep[id] = groupTaskItems(list)
  return { pre: groupTaskItems(pre), byStep }
}

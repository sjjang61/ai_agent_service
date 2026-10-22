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
  /** 같은 종류의 연속 작업을 합친 경우, 합쳐진 개별 작업 (파일 단위 등) */
  children?: TaskItem[]
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

const FAILED = /^\s*(error\b|\[tool error\]|\[mcp error\]|traceback)/i

/**
 * 단계 목록(호출·결과가 따로 나열됨)을 '작업' 목록으로 묶는다.
 * 호출과 결과는 도구 이름이 같은 가장 최근의 미완료 호출과 짝짓는다 (findPendingCall 과 같은 규칙).
 * 결과가 아직 없으면 running, 결과가 오류로 시작하면 failed, 그 밖에는 done. 분석(thought)은 그 자체로 done.
 */
export function buildTaskItems(steps: AgentStep[]): TaskItem[] {
  const items: TaskItem[] = []
  const pending: TaskItem[] = []
  for (const s of steps) {
    if (s.type === 'tool_call') {
      const item: TaskItem = {
        key: s.id,
        kind: 'tool',
        tool: s.tool,
        label: TASK_LABELS[s.tool ?? ''] ?? s.tool ?? '도구',
        summary: summarizeInput(s.tool, s.input),
        status: 'running',
        call: s,
      }
      items.push(item)
      pending.push(item)
    } else if (s.type === 'tool_result') {
      let idx = -1
      for (let i = pending.length - 1; i >= 0; i--) {
        if (pending[i].tool === s.tool) {
          idx = i
          break
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
  return groupTaskItems(items)
}

/** 지금 진행 중인 가장 안쪽(마지막) 작업 */
export function currentTask(items: TaskItem[]): TaskItem | null {
  for (let i = items.length - 1; i >= 0; i--) if (items[i].status === 'running') return items[i]
  return null
}

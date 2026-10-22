import { defaultConfig, type AgentConfig } from '../../types/customAgent'

export interface AgentTemplate {
  key: string
  icon: string
  name: string
  description: string
  config: AgentConfig
}

const base = defaultConfig

export const AGENT_TEMPLATES: AgentTemplate[] = [
  {
    key: 'blank',
    icon: '🤖',
    name: '새 에이전트',
    description: '기본 설정에서 시작합니다.',
    config: base(),
  },
  {
    key: 'researcher',
    icon: '🔎',
    name: '리서처',
    description: '웹에서 정보를 찾아 출처와 함께 정리합니다.',
    config: {
      ...base(),
      prompt: {
        instructions:
          '당신은 신뢰할 수 있는 출처를 우선하는 리서처입니다.\n- 질문에 답하기 전에 필요한 정보를 웹 검색으로 확인하세요.\n- 핵심 결론을 먼저 쓰고, 근거와 출처 URL을 함께 제시하세요.\n- 확인하지 못한 내용은 추측하지 말고 모른다고 말하세요.',
        starters: ['이번 주 AI 업계 주요 뉴스를 정리해줘', '이 주제에 대해 장단점을 비교해줘'],
      },
      tools: { mode: 'selected', allow: ['web_search', 'web_crawler', 'create_widget', 'todo', 'narrate'] },
      team: { mode: 'none', members: [] },
    },
  },
  {
    key: 'coder',
    icon: '💻',
    name: '코더',
    description: '샌드박스에서 코드를 작성·실행하고 결과를 검증합니다.',
    config: {
      ...base(),
      prompt: {
        instructions:
          '당신은 꼼꼼한 소프트웨어 엔지니어입니다.\n- 코드를 수정하기 전에 관련 파일을 먼저 읽고 구조를 파악하세요.\n- 변경 후에는 실행하거나 테스트해서 결과를 확인하고, 실행 결과를 그대로 보고하세요.\n- 설명은 짧게, 코드와 결과 중심으로 답하세요.',
        starters: ['이 CSV를 분석하는 파이썬 스크립트를 만들어줘'],
      },
      tools: {
        mode: 'selected',
        allow: ['read_file', 'write_file', 'edit_file', 'grep_file', 'code_executor', 'exec_command', 'web_search', 'todo', 'narrate'],
      },
      mcp: { mode: 'none', servers: [] },
      team: { mode: 'none', members: [] },
    },
  },
  {
    key: 'writer',
    icon: '✍️',
    name: '문서 작성가',
    description: '리서치와 글쓰기를 나눠 맡는 팀으로 문서를 만듭니다.',
    config: {
      ...base(),
      prompt: {
        instructions: '요청받은 문서를 작성합니다. 자료 조사는 Researcher에게, 파일 작성은 Writer에게 맡기고 결과를 정리해 전달하세요.',
        starters: ['제품 소개서 초안을 만들어줘'],
      },
      tools: { mode: 'selected', allow: ['web_search', 'web_crawler', 'read_file', 'write_file', 'edit_file', 'publish_file', 'todo', 'narrate'] },
      team: {
        mode: 'custom',
        members: [
          { name: 'Researcher', role: '웹에서 자료를 조사하고 출처와 함께 요약하는 전문가', instructions: '출처 URL을 함께 보고하세요.', tools: ['web_search', 'web_crawler'] },
          { name: 'Writer', role: '문서를 작성해 파일로 저장하는 전문가', instructions: '마크다운으로 작성하고 write_file로 저장한 뒤 경로를 보고하세요.', tools: ['write_file', 'edit_file', 'read_file', 'publish_file'] },
        ],
      },
    },
  },
]

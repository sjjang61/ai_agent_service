import { BookOpen, ClipboardList, ListChecks, MessageSquareHeart, NotebookPen, PencilLine, type LucideIcon } from 'lucide-react'

export interface PageTemplate {
  key: string
  title: string
  icon: LucideIcon
  color: string
  content: string
}

export const TEMPLATES: PageTemplate[] = [
  {
    key: 'guide',
    title: '페이지 사용 가이드',
    icon: BookOpen,
    color: '#3b82f6',
    content: `# 페이지 사용 가이드

페이지는 에이전트와 함께 작업한 내용을 정리해 두는 문서입니다. 마크다운으로 작성합니다.

## 기본 문법
- \`# 제목\`, \`## 소제목\` 으로 구조를 만듭니다.
- \`- 항목\` 으로 목록, \`1. 항목\` 으로 번호 목록을 만듭니다.
- \`- [ ] 할 일\` 로 체크리스트를 만듭니다.
- 표, 코드 블록(\`\`\`)도 사용할 수 있습니다.

## 팁
- 오른쪽 위의 **미리보기** 로 렌더링된 모습을 확인하세요.
- 변경 내용은 자동으로 저장됩니다.
- **공간** 에 페이지를 모아 프로젝트별로 정리할 수 있습니다.
`,
  },
  {
    key: 'feedback',
    title: '피드백 관리',
    icon: PencilLine,
    color: '#ef4444',
    content: `# 피드백 관리

| 날짜 | 출처 | 내용 | 우선순위 | 상태 |
|------|------|------|----------|------|
|      |      |      | 중       | 접수 |

## 반영 계획
- 

## 회고
- 
`,
  },
  {
    key: 'todo',
    title: '할 일 목록',
    icon: ListChecks,
    color: '#10b981',
    content: `# 할 일 목록

## 오늘
- [ ] 
- [ ] 

## 이번 주
- [ ] 

## 나중에
- [ ] 
`,
  },
  {
    key: 'project',
    title: '프로젝트 관리표',
    icon: ClipboardList,
    color: '#a855f7',
    content: `# 프로젝트 관리표

**목표:** 
**기간:** 
**담당:** 

## 마일스톤
| 단계 | 내용 | 기한 | 상태 |
|------|------|------|------|
| 1 |  |  | 대기 |
| 2 |  |  | 대기 |

## 리스크
- 

## 메모
- 
`,
  },
  {
    key: 'meeting',
    title: '회의록',
    icon: NotebookPen,
    color: '#f59e0b',
    content: `# 회의록

**일시:** 
**참석자:** 

## 안건
1. 

## 논의 내용
- 

## 결정 사항
- 

## 액션 아이템
- [ ] (담당자) 내용 — 기한
`,
  },
  {
    key: 'weekly',
    title: '주간 보고',
    icon: MessageSquareHeart,
    color: '#06b6d4',
    content: `# 주간 보고

## 이번 주 한 일
- 

## 다음 주 계획
- 

## 이슈 / 요청
- 
`,
  },
]

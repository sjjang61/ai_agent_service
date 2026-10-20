import type { TaskInput } from '../../types/schedule'

export interface TaskTemplate {
  emoji: string
  title: string
  description: string
  preset: Partial<TaskInput>
}

/** 빈 상태에 보여주는 예시. 이 앱의 에이전트가 실제로 할 수 있는 일(웹 검색·크롤링, sandbox 파일)로 구성했다. */
export const TASK_TEMPLATES: TaskTemplate[] = [
  {
    emoji: '🗞️',
    title: '뉴스 브리핑',
    description: '매일 아침 관심 분야의 주요 뉴스를 찾아 요약해줘.',
    preset: {
      name: '뉴스 브리핑',
      prompt: '오늘 AI·IT 분야의 주요 뉴스를 웹에서 검색해 5개로 요약하고, 각 항목에 출처 링크를 붙여줘.',
      schedule_type: 'daily',
      schedule_time: '08:30',
    },
  },
  {
    emoji: '🏷️',
    title: '가격 알림',
    description: '내가 고른 상품의 가격을 매일 확인하고 내려가면 알려줘.',
    preset: {
      name: '가격 알림',
      prompt: '[상품명]의 현재 최저가를 웹에서 확인해줘. 이전 실행 결과와 비교해서 가격이 내려갔으면 크게 알려주고, 변화가 없으면 한 줄로만 알려줘.',
      schedule_type: 'daily',
      schedule_time: '09:00',
    },
  },
  {
    emoji: '💱',
    title: '환율·시세 점검',
    description: '평일 아침 환율과 주요 지수를 확인해 한 줄로 요약해줘.',
    preset: {
      name: '환율·시세 점검',
      prompt: '오늘의 USD/KRW 환율과 코스피·나스닥 지수를 확인하고, 이전 실행과 비교해 변화를 한 줄로 요약해줘.',
      schedule_type: 'weekdays',
      schedule_time: '09:00',
    },
  },
  {
    emoji: '🔎',
    title: '웹페이지 변경 감지',
    description: '지정한 페이지를 확인해서 지난번과 달라진 점을 알려줘.',
    preset: {
      name: '웹페이지 변경 감지',
      prompt: '[URL]의 내용을 확인하고, 이전 실행 결과와 비교해 달라진 점만 알려줘. 달라진 점이 없으면 "변경 없음"이라고 답해줘.',
      schedule_type: 'daily',
      schedule_time: '10:00',
    },
  },
  {
    emoji: '📝',
    title: '주간 보고서',
    description: '매주 금요일 오후에 이번 주 작업을 정리한 보고서를 만들어줘.',
    preset: {
      name: '주간 보고서',
      prompt: '이번 주에 작업한 내용을 sandbox 작업공간(/workspace)의 파일을 훑어 정리하고, 주간 보고서(마크다운)를 만들어 저장한 뒤 다운로드 링크를 알려줘.',
      schedule_type: 'weekly',
      weekdays: [4],
      schedule_time: '17:00',
    },
  },
  {
    emoji: '🌤️',
    title: '주말 계획 짜기',
    description: '매주 목요일에 주말 날씨와 즐길 만한 활동을 추천해줘.',
    preset: {
      name: '주말 계획 짜기',
      prompt: '이번 주말 서울의 날씨와 열리는 행사를 검색해서, 즐길 만한 활동 3가지를 이유와 함께 추천해줘.',
      schedule_type: 'weekly',
      weekdays: [3],
      schedule_time: '18:00',
    },
  },
]

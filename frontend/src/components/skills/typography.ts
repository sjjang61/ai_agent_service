/** 맞춤 설정 화면 공통 글자 스타일 (스킬 화면 기준). 화면마다 크기·굵기를 따로 정하지 않고 이 값을 쓴다.
 *  페이지 제목(28px/semibold)과 설명(14px)은 SettingsPage / PageHeader 가 같은 값으로 그린다. */
export const T = {
  /** 목록·그룹 제목 (예: 설치됨, 서버 목록, 도구 그룹) */
  section: 'text-[17px] font-semibold text-content-primary',
  /** 항목(카드) 이름 */
  itemTitle: 'text-[14px] font-medium text-content-primary',
  /** 항목 설명 */
  itemDesc: 'text-[13px] text-content-secondary',
  /** 보조 정보 (메타, 도움말) */
  meta: 'text-xs text-content-tertiary',
} as const

/** 페이지 제목 줄 오른쪽의 주 버튼 (스킬 화면의 "추가" 버튼과 같은 모양) */
export const headerActionCls =
  'flex items-center gap-1.5 px-4 py-2 rounded-full bg-content-primary text-surface-primary text-[14px] font-medium border-none cursor-pointer hover:opacity-90 disabled:opacity-40'

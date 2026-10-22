import CustomizeLayout, { type CustomizeSection } from './CustomizeLayout'

interface Props {
  active: CustomizeSection
  title: string
  subtitle?: string
  /** 제목 줄 오른쪽에 놓는 버튼들 (스킬 화면의 "추가" 버튼 위치) */
  actions?: React.ReactNode
  children: React.ReactNode
}

/** 맞춤 설정 보조 사이드바 오른쪽 본문에 제목 + 스크롤 영역을 놓는 공통 페이지 틀.
 *  여백은 스킬 화면(PageHeader + 목록)과 같다: 제목 px-8 pt-8 pb-4, 본문 px-8 pb-10, 최대 너비 제한 없음(왼쪽 정렬). */
export default function SettingsPage({ active, title, subtitle, actions, children }: Props) {
  return (
    <CustomizeLayout active={active}>
      <div className="px-8 pt-8 pb-4 flex-shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-[28px] font-semibold text-content-primary flex-1">{title}</h1>
          {actions}
        </div>
        {subtitle && <p className="mt-1 text-[14px] text-content-secondary">{subtitle}</p>}
      </div>
      <div className="flex-1 overflow-y-auto px-8 pb-10">{children}</div>
    </CustomizeLayout>
  )
}

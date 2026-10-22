import CustomizeLayout, { type CustomizeSection } from './CustomizeLayout'

interface Props {
  active: CustomizeSection
  title: string
  subtitle?: string
  /** 본문 최대 너비(px) */
  maxWidth?: number
  children: React.ReactNode
}

/** 맞춤 설정 보조 사이드바 오른쪽 본문에 제목 + 스크롤 영역을 놓는 공통 페이지 틀 */
export default function SettingsPage({ active, title, subtitle, maxWidth = 1000, children }: Props) {
  return (
    <CustomizeLayout active={active}>
      <div className="px-8 pt-8 pb-4 flex-shrink-0">
        <h1 className="text-[28px] font-semibold text-content-primary">{title}</h1>
        {subtitle && <p className="mt-1 text-[14px] text-content-secondary">{subtitle}</p>}
      </div>
      <div className="flex-1 overflow-y-auto px-8 pb-10">
        <div className="mx-auto" style={{ maxWidth }}>
          {children}
        </div>
      </div>
    </CustomizeLayout>
  )
}

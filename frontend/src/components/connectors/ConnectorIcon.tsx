import { Calendar, FileText, HardDrive, Mail, Presentation, Table2 } from 'lucide-react'

const ICONS: Record<string, { icon: React.ReactNode; color: string }> = {
  gmail: { icon: <Mail size={22} />, color: '#ea4335' },
  google_calendar: { icon: <Calendar size={22} />, color: '#4285f4' },
  google_drive: { icon: <HardDrive size={22} />, color: '#0f9d58' },
  google_docs: { icon: <FileText size={22} />, color: '#4285f4' },
  google_sheets: { icon: <Table2 size={22} />, color: '#0f9d58' },
  google_slides: { icon: <Presentation size={22} />, color: '#f4b400' },
}

/** 커넥터 아이콘: 서비스 색의 아이콘을 흰 타일에 놓는다 */
export default function ConnectorIcon({ id, size = 44 }: { id: string; size?: number }) {
  const it = ICONS[id] ?? { icon: <Mail size={22} />, color: '#6b7280' }
  return (
    <span
      className="flex items-center justify-center rounded-[var(--radius-md)] border border-border bg-white flex-shrink-0"
      style={{ width: size, height: size, color: it.color }}
      aria-hidden
    >
      {it.icon}
    </span>
  )
}

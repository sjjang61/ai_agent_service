import {
  ArrowDown, BarChart3, Bot, CheckCircle2, Clock, Code2, Database, FileText, Globe, Mail, Search, Settings,
  Shield, Star, User, Users, type LucideIcon,
} from 'lucide-react'
import type { ProcessIconName, ProcessSpec } from '../../types/widget'

const ICONS: Record<Exclude<ProcessIconName, 'none'>, LucideIcon> = {
  bot: Bot, user: User, users: Users, file: FileText, check: CheckCircle2, search: Search, database: Database,
  chart: BarChart3, mail: Mail, code: Code2, clock: Clock, settings: Settings, globe: Globe, shield: Shield, star: Star,
}

/** 프로세스 다이어그램: 단계가 위에서 아래로 화살표로 이어지고, 한 단계의 여러 항목은 나란히 놓인다 */
export default function ProcessWidget({ spec }: { spec: ProcessSpec }) {
  return (
    <div className="rounded-[var(--radius-xl)] border border-border bg-surface-primary px-4 py-6 sm:px-8">
      <div className="flex flex-col items-center">
        {spec.stages.map((stage, si) => {
          const parallel = stage.items.length > 1
          return (
            <div key={si} className="w-full flex flex-col items-center">
              {si > 0 && <ArrowDown size={16} className="my-3 text-content-muted flex-shrink-0" aria-hidden />}
              <div
                className={`w-full grid gap-3 ${
                  parallel ? (stage.items.length === 2 ? 'sm:grid-cols-2' : stage.items.length === 3 ? 'sm:grid-cols-3' : 'sm:grid-cols-2 lg:grid-cols-4') : ''
                } ${stage.kind === 'result' ? 'rounded-[var(--radius-lg)] border border-border px-4 py-3.5' : ''}`}
              >
                {stage.items.map((it, ii) => {
                  const Icon = it.icon && it.icon !== 'none' ? ICONS[it.icon] : null
                  return (
                    <div
                      key={ii}
                      className={`flex flex-col items-center text-center px-4 py-3 rounded-[var(--radius-lg)] ${
                        it.highlight ? 'bg-accent-primary/15' : ''
                      }`}
                    >
                      {Icon && <Icon size={18} className="mb-2 text-content-primary" aria-hidden />}
                      <div className={`${stage.kind === 'result' ? 'text-[16px]' : 'text-[16px]'} font-semibold text-content-primary`}>
                        {it.title}
                      </div>
                      {it.description && <div className="mt-0.5 text-[13px] text-content-secondary">{it.description}</div>}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
      {spec.caption && <p className="mt-4 text-xs text-content-tertiary text-center">{spec.caption}</p>}
    </div>
  )
}

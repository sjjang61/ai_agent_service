import {
  Search,
  Folder,
  Terminal,
  Share2,
  BarChart3,
  Database,
  MessageCircle,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { toolsApi } from '../api/tools'
import SettingsPage from '../components/skills/SettingsPage'
import { T } from '../components/skills/typography'
import type { ToolGroup } from '../types/tool'

const ICON_MAP: Record<string, React.ReactNode> = {
  search: <Search size={18} />,
  folder: <Folder size={18} />,
  terminal: <Terminal size={18} />,
  share: <Share2 size={18} />,
  'bar-chart': <BarChart3 size={18} />,
  database: <Database size={18} />,
  'message-circle': <MessageCircle size={18} />,
}

export default function ToolsPage() {
  const { data: groups = [], isLoading } = useQuery<ToolGroup[]>({
    queryKey: ['tools'],
    queryFn: async () => (await toolsApi.list()).data,
  })

  return (
    <SettingsPage active="tools" title="도구" subtitle="에이전트가 작업 수행에 사용할 수 있는 도구 목록입니다.">
      <div className="space-y-6">
        {isLoading ? (
          <div className="text-content-secondary text-sm">Loading...</div>
        ) : (
          <div className="space-y-6">
            {groups.map((group) => (
              <div key={group.group} className="space-y-2">
                <div className="flex items-center gap-2 text-content-primary">
                  <span className="text-accent-primary">{ICON_MAP[group.icon] || <Folder size={18} />}</span>
                  <h2 className={T.section}>{group.label}</h2>
                  <span className="text-xs text-content-secondary bg-surface-tertiary px-2 py-0.5 rounded-full">
                    {group.tools.length}
                  </span>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                  {group.tools.map((tool) => (
                    <div
                      key={tool.name}
                      className="p-3 bg-surface-secondary border border-border rounded-lg hover:border-border-light transition-colors"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className={T.itemTitle}>
                            {tool.name}
                          </div>
                          <div className="mt-1 text-[13px] text-content-secondary whitespace-pre-wrap break-words">
                            {tool.description}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </SettingsPage>
  )
}

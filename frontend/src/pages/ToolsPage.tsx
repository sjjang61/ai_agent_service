import { Link } from 'react-router-dom'
import {
  ArrowLeft,
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
    <div className="min-h-screen bg-slate-900 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex items-center gap-3">
          <Link to="/" className="text-slate-400 hover:text-white transition-colors">
            <ArrowLeft size={20} />
          </Link>
          <h1 className="text-xl font-bold text-white">Tools</h1>
        </div>

        <p className="text-slate-400 text-sm">
          Agent가 작업 수행에 사용할 수 있는 도구 목록입니다.
        </p>

        {isLoading ? (
          <div className="text-slate-400 text-sm">Loading...</div>
        ) : (
          <div className="space-y-6">
            {groups.map((group) => (
              <div key={group.group} className="space-y-2">
                <div className="flex items-center gap-2 text-slate-300">
                  <span className="text-blue-400">{ICON_MAP[group.icon] || <Folder size={18} />}</span>
                  <h2 className="text-lg font-semibold">{group.label}</h2>
                  <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full">
                    {group.tools.length}
                  </span>
                </div>
                <div className="grid gap-2">
                  {group.tools.map((tool) => (
                    <div
                      key={tool.name}
                      className="p-3 bg-slate-800 border border-slate-700 rounded-lg hover:border-slate-600 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-white font-mono">
                            {tool.name}
                          </div>
                          <div className="text-xs text-slate-400 mt-1 leading-relaxed">
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
    </div>
  )
}

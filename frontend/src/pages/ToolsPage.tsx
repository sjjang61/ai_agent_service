import {
  Search,
  Folder,
  Terminal,
  Share2,
  BarChart3,
  Database,
  MessageCircle,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toolsApi } from '../api/tools'
import SettingsPage from '../components/skills/SettingsPage'
import { T } from '../components/skills/typography'
import { errorText } from '../components/skills/common'
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

function Switch({ on, onChange, label, disabled }: { on: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <button
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!on)}
      className={`relative flex-shrink-0 w-9 h-5 rounded-full border-none cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${on ? 'bg-accent-primary' : 'bg-surface-active'}`}
    >
      <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${on ? 'translate-x-4' : ''}`} />
    </button>
  )
}

export default function ToolsPage() {
  const qc = useQueryClient()
  const [error, setError] = useState('')
  const { data: groups = [], isLoading } = useQuery<ToolGroup[]>({
    queryKey: ['tools'],
    queryFn: async () => (await toolsApi.list()).data,
  })

  // 켜짐 상태를 화면에 먼저 반영하고, 서버에 저장하지 못하면 되돌린다
  const toggle = useMutation({
    mutationFn: ({ names, enabled }: { names: string[]; enabled: boolean }) =>
      names.length === 1 ? toolsApi.setEnabled(names[0], enabled) : toolsApi.setManyEnabled(names, enabled),
    onMutate: async ({ names, enabled }) => {
      setError('')
      await qc.cancelQueries({ queryKey: ['tools'] })
      const prev = qc.getQueryData<ToolGroup[]>(['tools'])
      qc.setQueryData<ToolGroup[]>(['tools'], (old) =>
        old?.map((g) => ({ ...g, tools: g.tools.map((t) => (names.includes(t.name) ? { ...t, enabled } : t)) }))
      )
      return { prev }
    },
    onError: (e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(['tools'], ctx.prev)
      setError(errorText(e, '도구 설정을 저장하지 못했습니다'))
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['tools'] }),
  })

  const all = groups.flatMap((g) => g.tools)
  const enabledCount = all.filter((t) => t.enabled).length

  return (
    <SettingsPage
      active="tools"
      title="도구"
      subtitle={`에이전트가 작업 수행에 사용할 수 있는 도구입니다. 끈 도구는 채팅·예약·메신저에서 쓰지 않습니다.${all.length ? ` (${all.length}개 중 ${enabledCount}개 사용)` : ''}`}
    >
      <div className="space-y-6">
        {error && <div className="text-[13px] text-red-500">{error}</div>}
        {isLoading ? (
          <div className="text-content-secondary text-sm">Loading...</div>
        ) : (
          <div className="space-y-6">
            {groups.map((group) => {
              const on = group.tools.filter((t) => t.enabled).length
              const names = group.tools.map((t) => t.name)
              return (
                <div key={group.group} className="space-y-2">
                  <div className="flex items-center gap-2 text-content-primary">
                    <span className="text-accent-primary">{ICON_MAP[group.icon] || <Folder size={18} />}</span>
                    <h2 className={T.section}>{group.label}</h2>
                    <span className="text-xs text-content-secondary bg-surface-tertiary px-2 py-0.5 rounded-full">
                      {on}/{group.tools.length}
                    </span>
                    <div className="flex-1" />
                    <button
                      onClick={() => toggle.mutate({ names, enabled: on < group.tools.length })}
                      className="text-xs text-content-tertiary hover:text-content-primary border-none bg-transparent cursor-pointer"
                    >
                      {on < group.tools.length ? '모두 켜기' : '모두 끄기'}
                    </button>
                  </div>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                    {group.tools.map((tool) => (
                      <div
                        key={tool.name}
                        className={`p-3 bg-surface-secondary border border-border rounded-lg hover:border-border-light transition-colors ${tool.enabled ? '' : 'opacity-55'}`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className={T.itemTitle}>
                              {tool.name}
                              {!tool.enabled && <span className="ml-2 text-[11px] font-normal text-content-muted">꺼짐</span>}
                            </div>
                            <div className="mt-1 text-[13px] text-content-secondary whitespace-pre-wrap break-words">
                              {tool.description}
                            </div>
                          </div>
                          <Switch
                            on={tool.enabled}
                            label={`${tool.name} ${tool.enabled ? '끄기' : '켜기'}`}
                            onChange={(v) => toggle.mutate({ names: [tool.name], enabled: v })}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </SettingsPage>
  )
}

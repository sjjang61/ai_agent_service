import { useEffect, useState } from 'react'
import { RefreshCw, Trash2, Edit2, CheckCircle, XCircle, Circle, Power } from 'lucide-react'
import { useMcpConfigs } from '../../hooks/useMcpConfig'
import { mcpApi } from '../../api/mcp'
import { useMcpStore } from '../../store/mcpStore'
import McpServerForm from './McpServerForm'
import { T } from '../skills/typography'
import type { MCPServer } from '../../types/mcp'

/** addTick: 페이지 제목 줄의 '서버 추가' 버튼을 누를 때마다 바뀌는 값. 바뀌면 등록 폼을 연다. */
export default function McpServerList({ addTick = 0 }: { addTick?: number }) {
  const { data: servers, isLoading, refetch } = useMcpConfigs()
  const { removeServer } = useMcpStore()
  const [showForm, setShowForm] = useState(false)
  const [editServer, setEditServer] = useState<MCPServer | null>(null)

  useEffect(() => {
    if (addTick > 0) {
      setEditServer(null)
      setShowForm(true)
    }
  }, [addTick])
  const [testResults, setTestResults] = useState<
    Record<string, { status: string; message?: string; tool_count?: number }>
  >({})
  const [testing, setTesting] = useState<string | null>(null)
  const [toggling, setToggling] = useState<string | null>(null)

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this MCP server?')) return
    await mcpApi.deleteConfig(id)
    removeServer(id)
    refetch()
  }

  const handleToggle = async (id: string) => {
    setToggling(id)
    try {
      await mcpApi.toggleConfig(id)
      refetch()
    } finally {
      setToggling(null)
    }
  }

  const handleTest = async (id: string) => {
    setTesting(id)
    try {
      const res = await mcpApi.testConfig(id)
      setTestResults((prev) => ({ ...prev, [id]: res.data }))
    } finally {
      setTesting(null)
    }
  }

  if (isLoading) {
    return <div className="text-content-tertiary text-sm">Loading...</div>
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className={T.section}>MCP Servers</h2>
      </div>

      {(showForm || editServer) && (
        <McpServerForm
          server={editServer}
          onClose={() => {
            setShowForm(false)
            setEditServer(null)
            refetch()
          }}
        />
      )}

      <div className="space-y-3">
        {servers?.map((server) => {
          const testResult = testResults[server.id]
          const isInactive = !server.is_active

          return (
            <div
              key={server.id}
              className={`rounded-[var(--radius-lg)] p-4 border transition-colors ${
                isInactive
                  ? 'bg-surface-secondary/40 border-border/50 opacity-60'
                  : 'bg-surface-secondary border-border hover:bg-surface-hover'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    {testResult?.status === 'connected' ? (
                      <CheckCircle size={15} className="text-accent-green flex-shrink-0" />
                    ) : testResult?.status === 'error' ? (
                      <XCircle size={15} className="text-accent-red flex-shrink-0" />
                    ) : (
                      <Circle size={15} className="text-content-muted flex-shrink-0" />
                    )}
                    <span
                      className={`font-medium text-[14px] ${
                        isInactive ? 'text-content-tertiary' : 'text-content-primary'
                      }`}
                    >
                      {server.display_name}
                    </span>
                    <span className="text-[11px] bg-surface-tertiary px-2 py-0.5 rounded-[var(--radius-sm)]
                      text-content-secondary border border-border/50">
                      {server.transport}
                    </span>
                    {/* Active/Inactive Badge */}
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded-[var(--radius-sm)] border font-medium ${
                        isInactive
                          ? 'bg-surface-tertiary/50 text-content-muted border-border/50'
                          : 'bg-accent-green/10 text-accent-green border-accent-green/30'
                      }`}
                    >
                      {isInactive ? 'Inactive' : 'Active'}
                    </span>
                    {testResult?.tool_count !== undefined && (
                      <span className="text-xs text-accent-green">
                        {testResult.tool_count} tools
                      </span>
                    )}
                  </div>
                  {server.command && (
                    <p className="text-xs text-content-tertiary mt-1 font-mono truncate">
                      {server.command} {server.args?.join(' ')}
                    </p>
                  )}
                  {server.url && (
                    <p className="text-xs text-content-tertiary mt-1 font-mono truncate">
                      {server.url}
                    </p>
                  )}
                  {testResult?.status === 'error' && testResult.message && (
                    <p className="text-xs text-accent-red mt-1">{testResult.message}</p>
                  )}
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  {/* Active/Inactive Toggle */}
                  <button
                    onClick={() => handleToggle(server.id)}
                    disabled={toggling === server.id}
                    className={`p-1.5 transition-colors disabled:opacity-50 rounded-[var(--radius-sm)] ${
                      isInactive
                        ? 'text-content-muted hover:text-accent-green hover:bg-surface-hover'
                        : 'text-accent-green hover:text-content-muted hover:bg-surface-hover'
                    }`}
                    title={isInactive ? 'Activate' : 'Deactivate'}
                  >
                    <Power
                      size={14}
                      className={toggling === server.id ? 'animate-pulse' : ''}
                    />
                  </button>
                  {/* Connection Test (only when active) */}
                  {!isInactive && (
                    <button
                      onClick={() => handleTest(server.id)}
                      disabled={testing === server.id}
                      className="p-1.5 text-content-secondary hover:text-accent-primary
                        hover:bg-surface-hover transition-colors disabled:opacity-50
                        rounded-[var(--radius-sm)]"
                      title="Test connection"
                    >
                      <RefreshCw
                        size={14}
                        className={testing === server.id ? 'animate-spin' : ''}
                      />
                    </button>
                  )}
                  <button
                    onClick={() => setEditServer(server)}
                    className="p-1.5 text-content-secondary hover:text-content-primary
                      hover:bg-surface-hover transition-colors rounded-[var(--radius-sm)]"
                    title="Edit"
                  >
                    <Edit2 size={14} />
                  </button>
                  <button
                    onClick={() => handleDelete(server.id)}
                    className="p-1.5 text-content-secondary hover:text-accent-red
                      hover:bg-surface-hover transition-colors rounded-[var(--radius-sm)]"
                    title="Delete"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </div>
          )
        })}
        {(!servers || servers.length === 0) && !showForm && (
          <div className="text-center text-content-muted py-12 border border-dashed border-border
            rounded-[var(--radius-lg)] bg-surface-secondary/30">
            <p className="text-sm">No MCP servers configured.</p>
            <p className="text-xs mt-1">Add one to extend Agent capabilities.</p>
          </div>
        )}
      </div>
    </div>
  )
}

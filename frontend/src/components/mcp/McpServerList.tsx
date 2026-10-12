import { useState } from 'react'
import { Plus, RefreshCw, Trash2, Edit2, CheckCircle, XCircle, Circle, Power } from 'lucide-react'
import { useMcpConfigs } from '../../hooks/useMcpConfig'
import { mcpApi } from '../../api/mcp'
import { useMcpStore } from '../../store/mcpStore'
import McpServerForm from './McpServerForm'
import type { MCPServer } from '../../types/mcp'

export default function McpServerList() {
  const { data: servers, isLoading, refetch } = useMcpConfigs()
  const { removeServer } = useMcpStore()
  const [showForm, setShowForm] = useState(false)
  const [editServer, setEditServer] = useState<MCPServer | null>(null)
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
    return <div className="text-slate-400 text-sm">Loading...</div>
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold text-white">MCP Servers</h2>
        <button
          onClick={() => {
            setEditServer(null)
            setShowForm(true)
          }}
          className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm transition-colors"
        >
          <Plus size={14} />
          Add Server
        </button>
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
              className={`rounded-xl p-4 border transition-colors ${
                isInactive
                  ? 'bg-slate-800/40 border-slate-700/50 opacity-60'
                  : 'bg-slate-800 border-slate-700'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    {testResult?.status === 'connected' ? (
                      <CheckCircle size={15} className="text-green-400 flex-shrink-0" />
                    ) : testResult?.status === 'error' ? (
                      <XCircle size={15} className="text-red-400 flex-shrink-0" />
                    ) : (
                      <Circle size={15} className="text-slate-500 flex-shrink-0" />
                    )}
                    <span className={`font-medium ${isInactive ? 'text-slate-400' : 'text-white'}`}>
                      {server.display_name}
                    </span>
                    <span className="text-xs bg-slate-700 px-2 py-0.5 rounded text-slate-400">
                      {server.transport}
                    </span>
                    {/* 활성/비활성 뱃지 */}
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${
                        isInactive
                          ? 'bg-slate-700/50 text-slate-500 border-slate-600/50'
                          : 'bg-green-500/10 text-green-400 border-green-500/30'
                      }`}
                    >
                      {isInactive ? '비활성' : '활성'}
                    </span>
                    {testResult?.tool_count !== undefined && (
                      <span className="text-xs text-green-400">
                        {testResult.tool_count} tools
                      </span>
                    )}
                  </div>
                  {server.command && (
                    <p className="text-xs text-slate-500 mt-1 font-mono truncate">
                      {server.command} {server.args?.join(' ')}
                    </p>
                  )}
                  {server.url && (
                    <p className="text-xs text-slate-500 mt-1 font-mono truncate">
                      {server.url}
                    </p>
                  )}
                  {testResult?.status === 'error' && testResult.message && (
                    <p className="text-xs text-red-400 mt-1">{testResult.message}</p>
                  )}
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  {/* 활성/비활성 토글 */}
                  <button
                    onClick={() => handleToggle(server.id)}
                    disabled={toggling === server.id}
                    className={`p-1.5 transition-colors disabled:opacity-50 ${
                      isInactive
                        ? 'text-slate-500 hover:text-green-400'
                        : 'text-green-400 hover:text-slate-400'
                    }`}
                    title={isInactive ? '활성화' : '비활성화'}
                  >
                    <Power
                      size={14}
                      className={toggling === server.id ? 'animate-pulse' : ''}
                    />
                  </button>
                  {/* 연결 테스트 (활성 상태일 때만) */}
                  {!isInactive && (
                    <button
                      onClick={() => handleTest(server.id)}
                      disabled={testing === server.id}
                      className="p-1.5 text-slate-400 hover:text-blue-400 transition-colors disabled:opacity-50"
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
                    className="p-1.5 text-slate-400 hover:text-white transition-colors"
                    title="Edit"
                  >
                    <Edit2 size={14} />
                  </button>
                  <button
                    onClick={() => handleDelete(server.id)}
                    className="p-1.5 text-slate-400 hover:text-red-400 transition-colors"
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
          <div className="text-center text-slate-500 py-12 border border-dashed border-slate-700 rounded-xl">
            <p className="text-sm">No MCP servers configured.</p>
            <p className="text-xs mt-1">Add one to extend Agent capabilities.</p>
          </div>
        )}
      </div>
    </div>
  )
}

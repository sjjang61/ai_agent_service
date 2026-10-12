import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { X, Plus, Trash2 } from 'lucide-react'
import { mcpApi } from '../../api/mcp'
import type { MCPServer } from '../../types/mcp'

interface FormData {
  name: string
  display_name: string
  transport: string
  command: string
  args_str: string
  url: string
}

export default function McpServerForm({
  server,
  onClose,
}: {
  server: MCPServer | null
  onClose: () => void
}) {
  const { register, handleSubmit, watch } = useForm<FormData>({
    defaultValues: {
      name: server?.name || '',
      display_name: server?.display_name || '',
      transport: server?.transport || 'stdio',
      command: server?.command || '',
      args_str: server?.args?.join(' ') || '',
      url: server?.url || '',
    },
  })
  const [envVars, setEnvVars] = useState<[string, string][]>([['', '']])
  const [submitting, setSubmitting] = useState(false)
  const transport = watch('transport')

  const onSubmit = async (data: FormData) => {
    setSubmitting(true)
    try {
      const env = Object.fromEntries(envVars.filter(([k]) => k.trim()))
      const payload = {
        name: data.name,
        display_name: data.display_name,
        transport: data.transport,
        command: data.command || undefined,
        args: data.args_str ? data.args_str.split(' ').filter(Boolean) : [],
        url: data.url || undefined,
        env,
      }
      if (server) {
        await mcpApi.updateConfig(server.id, payload)
      } else {
        await mcpApi.createConfig(payload)
      }
      onClose()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="bg-slate-800 border border-slate-600 rounded-xl p-5">
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-semibold text-white">
          {server ? 'Edit MCP Server' : 'Add MCP Server'}
        </h3>
        <button onClick={onClose} className="text-slate-400 hover:text-white">
          <X size={16} />
        </button>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Name (ID)</label>
            <input
              {...register('name')}
              className="w-full px-3 py-1.5 bg-slate-700 text-white rounded text-sm border border-slate-600 focus:outline-none focus:border-blue-500"
              placeholder="filesystem-server"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Display Name</label>
            <input
              {...register('display_name')}
              className="w-full px-3 py-1.5 bg-slate-700 text-white rounded text-sm border border-slate-600 focus:outline-none focus:border-blue-500"
              placeholder="Filesystem Server"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs text-slate-400 mb-1">Transport</label>
          <select
            {...register('transport')}
            className="w-full px-3 py-1.5 bg-slate-700 text-white rounded text-sm border border-slate-600"
          >
            <option value="stdio">stdio</option>
            <option value="sse">SSE (Legacy)</option>
            <option value="streamable">Streamable HTTP</option>
          </select>
        </div>

        {transport === 'stdio' ? (
          <>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Command</label>
              <input
                {...register('command')}
                className="w-full px-3 py-1.5 bg-slate-700 text-white rounded text-sm border border-slate-600 focus:outline-none focus:border-blue-500 font-mono"
                placeholder="uvx mcp-server-filesystem"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">
                Args (space separated)
              </label>
              <input
                {...register('args_str')}
                className="w-full px-3 py-1.5 bg-slate-700 text-white rounded text-sm border border-slate-600 focus:outline-none focus:border-blue-500 font-mono"
                placeholder="/home/user/workspace"
              />
            </div>
          </>
        ) : (
          <div>
            <label className="block text-xs text-slate-400 mb-1">URL</label>
            <input
              {...register('url')}
              className="w-full px-3 py-1.5 bg-slate-700 text-white rounded text-sm border border-slate-600 focus:outline-none focus:border-blue-500"
              placeholder={
                transport === 'streamable'
                  ? 'http://localhost:3001/mcp'
                  : 'http://localhost:3001/sse'
              }
            />
            {transport === 'streamable' && (
              <p className="text-[10px] text-slate-500 mt-1">
                MCP Streamable HTTP (2025-03-26 spec) — 엔드포인트 URL 입력
              </p>
            )}
          </div>
        )}

        <div>
          <div className="flex justify-between items-center mb-1.5">
            <label className="text-xs text-slate-400">Environment Variables</label>
            <button
              type="button"
              onClick={() => setEnvVars([...envVars, ['', '']])}
              className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
            >
              <Plus size={10} /> Add
            </button>
          </div>
          {envVars.map((pair, i) => (
            <div key={i} className="flex gap-2 mb-1.5">
              <input
                value={pair[0]}
                onChange={(e) => {
                  const n = [...envVars] as [string, string][]
                  n[i] = [e.target.value, n[i][1]]
                  setEnvVars(n)
                }}
                placeholder="KEY"
                className="w-2/5 px-2 py-1 bg-slate-700 text-white rounded text-xs border border-slate-600 font-mono"
              />
              <input
                value={pair[1]}
                onChange={(e) => {
                  const n = [...envVars] as [string, string][]
                  n[i] = [n[i][0], e.target.value]
                  setEnvVars(n)
                }}
                placeholder="VALUE"
                className="flex-1 px-2 py-1 bg-slate-700 text-white rounded text-xs border border-slate-600"
              />
              <button
                type="button"
                onClick={() => setEnvVars(envVars.filter((_, j) => j !== i))}
                className="text-red-400 hover:text-red-300"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>

        <div className="flex gap-2 justify-end pt-1">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-slate-400 hover:text-white text-sm transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm transition-colors"
          >
            {submitting ? 'Saving...' : server ? 'Update' : 'Save & Connect'}
          </button>
        </div>
      </form>
    </div>
  )
}

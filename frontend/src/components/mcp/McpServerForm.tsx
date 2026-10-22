import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Plus, Trash2, ExternalLink } from 'lucide-react'
import { MCP_PRESETS, type McpPreset } from './mcpPresets'
import { Modal, inputCls, primaryBtn } from '../skills/common'
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
  const { register, handleSubmit, watch, setValue } = useForm<FormData>({
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
  const [preset, setPreset] = useState<McpPreset | null>(null)

  const applyPreset = (p: McpPreset) => {
    setPreset(p)
    setValue('name', p.name)
    setValue('display_name', p.display_name)
    setValue('transport', 'stdio')
    setValue('command', p.command)
    setValue('args_str', p.args.join(' '))
    setEnvVars(p.env.length ? p.env.map((e) => [e.key, ''] as [string, string]) : [['', '']])
  }

  const onSubmit = async (data: FormData) => {
    setSubmitting(true)
    try {
      // 키가 없거나 값이 빈 항목은 보내지 않는다 (빈 값이 서버의 기본값을 덮어쓰지 않게)
      const env = Object.fromEntries(envVars.filter(([k, v]) => k.trim() && v.trim()))
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
    <Modal title={server ? 'Edit MCP Server' : 'Add MCP Server'} onClose={onClose}>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {!server && (
          <div>
            <div className="text-[13px] text-content-secondary mb-1.5">자주 쓰는 서버에서 시작</div>
            <div className="flex flex-wrap gap-2">
              {MCP_PRESETS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => applyPreset(p)}
                  title={p.description}
                  className={`px-3.5 py-1.5 rounded-full text-[13px] border cursor-pointer transition-colors ${
                    preset?.id === p.id
                      ? 'bg-accent-primary/10 border-accent-primary text-accent-primary'
                      : 'bg-transparent border-border text-content-secondary hover:bg-surface-hover hover:text-content-primary'
                  }`}
                >
                  {p.display_name}
                </button>
              ))}
            </div>
            {preset && (
              <div className="mt-3 p-3.5 rounded-[var(--radius-md)] bg-surface-secondary border border-border">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[13px] font-medium text-content-primary">{preset.description}</span>
                  <a href={preset.docsUrl} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-xs text-accent-primary hover:text-accent-hover">
                    문서 <ExternalLink size={11} />
                  </a>
                </div>
                <div className="mt-2 text-xs text-content-tertiary">인증 준비</div>
                <ol className="mt-1 pl-4 list-decimal space-y-1 text-xs text-content-secondary">
                  {preset.authSteps.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-[13px] text-content-secondary mb-1.5">Name (ID)</label>
            <input
              {...register('name')}
              className={`${inputCls}`}
              placeholder="filesystem-server"
            />
          </div>
          <div>
            <label className="block text-[13px] text-content-secondary mb-1.5">Display Name</label>
            <input
              {...register('display_name')}
              className={`${inputCls}`}
              placeholder="Filesystem Server"
            />
          </div>
        </div>

        <div>
          <label className="block text-[13px] text-content-secondary mb-1.5">Transport</label>
          <select
            {...register('transport')}
            className={`${inputCls}`}
          >
            <option value="stdio">stdio</option>
            <option value="sse">SSE (Legacy)</option>
            <option value="streamable">Streamable HTTP</option>
          </select>
        </div>

        {transport === 'stdio' ? (
          <>
            <div>
              <label className="block text-[13px] text-content-secondary mb-1.5">Command</label>
              <input
                {...register('command')}
                className={`${inputCls} font-mono`}
                placeholder="uvx mcp-server-filesystem"
              />
            </div>
            <div>
              <label className="block text-[13px] text-content-secondary mb-1.5">
                Args (space separated)
              </label>
              <input
                {...register('args_str')}
                className={`${inputCls} font-mono`}
                placeholder="/home/user/workspace"
              />
            </div>
          </>
        ) : (
          <div>
            <label className="block text-[13px] text-content-secondary mb-1.5">URL</label>
            <input
              {...register('url')}
              className={`${inputCls}`}
              placeholder={
                transport === 'streamable'
                  ? 'http://localhost:3001/mcp'
                  : 'http://localhost:3001/sse'
              }
            />
            {transport === 'streamable' && (
              <p className="text-xs text-content-muted mt-1.5">
                MCP Streamable HTTP (2025-03-26 spec) — 엔드포인트 URL 입력
              </p>
            )}
          </div>
        )}

        <div>
          <div className="flex justify-between items-center mb-1.5">
            <label className="text-[13px] text-content-secondary">Environment Variables</label>
            <button
              type="button"
              onClick={() => setEnvVars([...envVars, ['', '']])}
              className="text-[13px] text-accent-primary hover:text-accent-hover flex items-center gap-1 border-none bg-transparent cursor-pointer"
            >
              <Plus size={10} /> Add
            </button>
          </div>
          {envVars.map((pair, i) => (
            <div key={i} className="mb-2">
            <div className="grid grid-cols-[2fr_3fr_auto] items-center gap-2">
              <input
                value={pair[0]}
                onChange={(e) => {
                  const n = [...envVars] as [string, string][]
                  n[i] = [e.target.value, n[i][1]]
                  setEnvVars(n)
                }}
                placeholder="KEY"
                className={`${inputCls} font-mono`}
              />
              <input
                value={pair[1]}
                onChange={(e) => {
                  const n = [...envVars] as [string, string][]
                  n[i] = [n[i][0], e.target.value]
                  setEnvVars(n)
                }}
                placeholder={preset?.env.find((x) => x.key === pair[0])?.optional ? 'VALUE (선택)' : 'VALUE'}
                className={inputCls}
              />
              <button
                type="button"
                onClick={() => setEnvVars(envVars.filter((_, j) => j !== i))}
                className="p-1.5 text-content-muted hover:text-accent-red border-none bg-transparent cursor-pointer"
              >
                <Trash2 size={12} />
              </button>
            </div>
            {preset?.env.find((x) => x.key === pair[0]) && (
              <p className="mt-1 text-xs text-content-muted">{preset.env.find((x) => x.key === pair[0])!.hint}</p>
            )}
            </div>
          ))}
        </div>

        <div className="flex gap-2 justify-end pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2.5 text-[13px] text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className={primaryBtn}
          >
            {submitting ? 'Saving...' : server ? 'Update' : 'Save & Connect'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

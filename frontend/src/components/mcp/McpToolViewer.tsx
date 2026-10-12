import { useQuery } from '@tanstack/react-query'
import { mcpApi } from '../../api/mcp'
import type { MCPTool } from '../../types/mcp'

export default function McpToolViewer({ serverId }: { serverId: string }) {
  const { data: tools, isLoading } = useQuery({
    queryKey: ['mcp-tools', serverId],
    queryFn: () => mcpApi.getTools(serverId).then((r) => r.data as MCPTool[]),
  })

  if (isLoading) return <div className="text-xs text-slate-400">Loading tools...</div>

  return (
    <div className="space-y-1 mt-2">
      {tools?.map((tool) => (
        <div key={tool.name} className="text-xs bg-slate-700 rounded px-2 py-1.5 flex gap-2">
          <span className="text-blue-400 font-mono flex-shrink-0">{tool.name}</span>
          <span className="text-slate-400">{tool.description}</span>
        </div>
      ))}
    </div>
  )
}

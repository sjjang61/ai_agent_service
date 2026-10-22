import { useQuery } from '@tanstack/react-query'
import { mcpApi } from '../../api/mcp'
import type { MCPTool } from '../../types/mcp'

export default function McpToolViewer({ serverId }: { serverId: string }) {
  const { data: tools, isLoading } = useQuery({
    queryKey: ['mcp-tools', serverId],
    queryFn: () => mcpApi.getTools(serverId).then((r) => r.data as MCPTool[]),
  })

  if (isLoading) return <div className="text-xs text-content-tertiary">Loading tools...</div>

  return (
    <div className="space-y-1 mt-2">
      {tools?.map((tool) => (
        <div key={tool.name} className="text-xs bg-surface-tertiary rounded-[var(--radius-sm)] px-2 py-1.5 flex gap-2">
          <span className="text-accent-primary font-mono flex-shrink-0">{tool.name}</span>
          <span className="text-content-secondary">{tool.description}</span>
        </div>
      ))}
    </div>
  )
}

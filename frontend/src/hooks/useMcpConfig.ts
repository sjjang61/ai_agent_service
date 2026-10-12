import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { mcpApi } from '../api/mcp'
import { useMcpStore } from '../store/mcpStore'
import type { MCPServer } from '../types/mcp'

export function useMcpConfigs() {
  const { setServers } = useMcpStore()
  const query = useQuery({
    queryKey: ['mcp-configs'],
    queryFn: () => mcpApi.getConfigs().then((r) => r.data as MCPServer[]),
  })
  useEffect(() => {
    if (query.data) setServers(query.data)
  }, [query.data, setServers])
  return query
}

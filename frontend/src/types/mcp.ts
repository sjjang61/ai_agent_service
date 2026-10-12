export interface MCPServer {
  id: string
  name: string
  display_name: string
  transport: 'stdio' | 'sse' | 'websocket'
  command?: string
  args: string[]
  url?: string
  is_active: boolean
  created_at: string
}

export interface MCPTool {
  name: string
  description: string
  input_schema: Record<string, unknown>
}

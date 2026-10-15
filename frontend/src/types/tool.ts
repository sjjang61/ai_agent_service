export interface ToolInfo {
  name: string
  description: string
  group: string
}

export interface ToolGroup {
  group: string
  label: string
  icon: string
  tools: ToolInfo[]
}

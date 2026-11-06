export interface ToolInfo {
  name: string
  description: string
  group: string
  /** 사용자가 켜 두었는지 (끄면 에이전트가 쓰지 못한다) */
  enabled: boolean
}

export interface ToolGroup {
  group: string
  label: string
  icon: string
  tools: ToolInfo[]
}

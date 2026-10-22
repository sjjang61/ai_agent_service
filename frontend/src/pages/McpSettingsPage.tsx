import SettingsPage from '../components/skills/SettingsPage'
import McpServerList from '../components/mcp/McpServerList'

export default function McpSettingsPage() {
  return (
    <SettingsPage active="mcp" title="MCP 설정" subtitle="외부 도구를 연결하는 MCP 서버를 등록하고 관리합니다.">
      <McpServerList />
    </SettingsPage>
  )
}

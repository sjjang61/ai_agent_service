import { useState } from 'react'
import { Plus } from 'lucide-react'
import SettingsPage from '../components/skills/SettingsPage'
import { headerActionCls } from '../components/skills/typography'
import McpServerList from '../components/mcp/McpServerList'

export default function McpSettingsPage() {
  // 제목 줄의 추가 버튼을 누를 때마다 값이 바뀌어 목록 쪽에서 등록 폼을 연다
  const [addTick, setAddTick] = useState(0)
  return (
    <SettingsPage
      active="mcp"
      title="MCP 설정"
      subtitle="외부 도구를 연결하는 MCP 서버를 등록하고 관리합니다."
      actions={
        <button onClick={() => setAddTick((n) => n + 1)} className={headerActionCls}>
          <Plus size={14} /> 서버 추가
        </button>
      }
    >
      <McpServerList addTick={addTick} />
    </SettingsPage>
  )
}

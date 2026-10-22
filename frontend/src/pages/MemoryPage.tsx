import SettingsPage from '../components/skills/SettingsPage'
import MemoryList from '../components/memory/MemoryList'

export default function MemoryPage() {
  return (
    <SettingsPage active="memory" title="메모리" subtitle="에이전트가 기억하는 사용자 정보를 확인하고 관리합니다." maxWidth={900}>
      <MemoryList />
    </SettingsPage>
  )
}

import SettingsPage from '../components/skills/SettingsPage'
import SandboxStatus from '../components/sandbox/SandboxStatus'
import ArtifactsPanel from '../components/sandbox/ArtifactsPanel'

export default function SandboxPage() {
  return (
    <SettingsPage active="sandbox" title="샌드박스" subtitle="에이전트가 코드를 실행하는 격리 환경과 그 안의 파일을 확인합니다.">
      <div className="space-y-4">
        <SandboxStatus />
        <ArtifactsPanel />
      </div>
    </SettingsPage>
  )
}

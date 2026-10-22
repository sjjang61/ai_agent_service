import SettingsPage from '../components/skills/SettingsPage'
import SandboxStatus from '../components/sandbox/SandboxStatus'
import SandboxInstances from '../components/sandbox/SandboxInstances'
import ArtifactsPanel from '../components/sandbox/ArtifactsPanel'
import { T } from '../components/skills/typography'

export default function SandboxPage() {
  return (
    <SettingsPage active="sandbox" title="샌드박스" subtitle="대화방마다 독립된 격리 환경에서 에이전트가 코드를 실행합니다. 스페이스 대화는 공용 sandbox 를 함께 씁니다.">
      <div className="space-y-4">
        <SandboxInstances />
        <h2 className={`${T.section} pt-2`}>공용 sandbox</h2>
        <SandboxStatus />
        <ArtifactsPanel />
      </div>
    </SettingsPage>
  )
}

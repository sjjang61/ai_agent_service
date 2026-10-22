import SettingsPage from '../components/skills/SettingsPage'
import WikiList from '../components/wiki/WikiList'

export default function WikiPage() {
  return (
    <SettingsPage active="wiki" title="위키" subtitle="대화에서 저장한 내용을 정리해 두는 개인 위키입니다." maxWidth={1200}>
      <WikiList />
    </SettingsPage>
  )
}

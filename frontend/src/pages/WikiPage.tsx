import { useState } from 'react'
import { Plus } from 'lucide-react'
import SettingsPage from '../components/skills/SettingsPage'
import { headerActionCls } from '../components/skills/typography'
import WikiList from '../components/wiki/WikiList'

export default function WikiPage() {
  // 제목 줄의 추가 버튼을 누를 때마다 값이 바뀌어 목록 쪽에서 입력 폼을 연다
  const [addTick, setAddTick] = useState(0)
  return (
    <SettingsPage
      active="wiki"
      title="위키"
      subtitle="대화에서 저장한 내용을 정리해 두는 개인 위키입니다."
      actions={
        <button onClick={() => setAddTick((n) => n + 1)} className={headerActionCls}>
          <Plus size={14} /> 새 항목
        </button>
      }
    >
      <WikiList addTick={addTick} />
    </SettingsPage>
  )
}

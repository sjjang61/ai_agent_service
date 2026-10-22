import { useState } from 'react'
import { Plus } from 'lucide-react'
import SettingsPage from '../components/skills/SettingsPage'
import { headerActionCls } from '../components/skills/typography'
import MemoryList from '../components/memory/MemoryList'

export default function MemoryPage() {
  // 제목 줄의 추가 버튼을 누를 때마다 값이 바뀌어 목록 쪽에서 입력 폼을 연다
  const [addTick, setAddTick] = useState(0)
  return (
    <SettingsPage
      active="memory"
      title="메모리"
      subtitle="에이전트가 기억하는 사용자 정보를 확인하고 관리합니다."
      actions={
        <button onClick={() => setAddTick((n) => n + 1)} className={headerActionCls}>
          <Plus size={14} /> 메모리 추가
        </button>
      }
    >
      <MemoryList addTick={addTick} />
    </SettingsPage>
  )
}

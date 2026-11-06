import { useState } from 'react'
import { Plus } from 'lucide-react'
import SettingsPage from '../components/skills/SettingsPage'
import { headerActionCls } from '../components/skills/typography'
import WikiList from '../components/wiki/WikiList'
import WikiGraphView from '../components/wiki/WikiGraphView'

export default function WikiPage() {
  // 제목 줄의 추가 버튼을 누를 때마다 값이 바뀌어 목록 쪽에서 입력 폼을 연다
  const [addTick, setAddTick] = useState(0)
  const [tab, setTab] = useState<'list' | 'graph'>('list')
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
      <div className="flex gap-1 border-b border-border mb-4">
        {([['list', '목록'], ['graph', '지식 그래프']] as const).map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-4 py-2 text-sm border-b-2 -mb-px transition-colors ${tab === k ? 'border-accent-primary text-content-primary' : 'border-transparent text-content-muted hover:text-content-primary'}`}>
            {label}
          </button>
        ))}
      </div>
      {tab === 'list' ? <WikiList addTick={addTick} /> : <WikiGraphView />}
    </SettingsPage>
  )
}

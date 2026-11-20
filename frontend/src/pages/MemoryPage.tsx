import { useState } from 'react'
import { Plus } from 'lucide-react'
import SettingsPage from '../components/skills/SettingsPage'
import { headerActionCls } from '../components/skills/typography'
import MemoryList from '../components/memory/MemoryList'
import ProfileEditor from '../components/memory/ProfileEditor'
import JournalView from '../components/memory/JournalView'
import TopicsView from '../components/memory/TopicsView'

type Tab = 'profile' | 'items' | 'journal' | 'topics'
const TABS: { key: Tab; label: string; hint: string }[] = [
  { key: 'profile', label: 'USER', hint: '성향·배경' },
  { key: 'items', label: '메모리', hint: '사실·작업 방식·단기' },
  { key: 'journal', label: 'Episodes', hint: '날짜별 일지' },
  { key: 'topics', label: 'Topics', hint: '전문 지식' },
]

export default function MemoryPage() {
  // 제목 줄의 추가 버튼을 누를 때마다 값이 바뀌어 목록 쪽에서 입력 폼을 연다
  const [addTick, setAddTick] = useState(0)
  const [tab, setTab] = useState<Tab>(() => {
    try { return (localStorage.getItem('memory-tab') as Tab) || 'items' } catch { return 'items' }
  })
  const pick = (t: Tab) => {
    setTab(t)
    try { localStorage.setItem('memory-tab', t) } catch { /* 저장하지 못해도 동작한다 */ }
  }
  return (
    <SettingsPage
      active="memory"
      title="메모리"
      subtitle="에이전트가 기억하는 사용자 정보를 확인하고 관리합니다."
      actions={
        tab === 'items' ? (
          <button onClick={() => setAddTick((n) => n + 1)} className={headerActionCls}>
            <Plus size={14} /> 메모리 추가
          </button>
        ) : undefined
      }
    >
      <div role="tablist" className="flex flex-wrap gap-1 mb-5 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => pick(t.key)}
            title={t.hint}
            className={`px-4 py-2 text-[14px] border-none bg-transparent cursor-pointer -mb-px border-b-2 ${tab === t.key ? 'text-content-primary font-medium border-b-content-primary' : 'text-content-secondary hover:text-content-primary border-b-transparent'}`}
            style={{ borderBottomStyle: 'solid', borderBottomWidth: 2 }}
          >
            {t.label}
            <span className="ml-1.5 text-xs text-content-tertiary">{t.hint}</span>
          </button>
        ))}
      </div>
      {tab === 'profile' && <ProfileEditor />}
      {tab === 'items' && <MemoryList addTick={addTick} />}
      {tab === 'journal' && <JournalView />}
      {tab === 'topics' && <TopicsView />}
    </SettingsPage>
  )
}

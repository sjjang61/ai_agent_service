import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { siteProfilesApi, type SiteProfiles } from '../api/siteProfiles'
import SettingsPage from '../components/skills/SettingsPage'
import { T } from '../components/skills/typography'
import SiteEditor from '../components/sites/SiteEditor'
import VerticalEditor from '../components/sites/VerticalEditor'
import StatusBadge from '../components/sites/StatusBadge'
import { secondaryBtn } from '../components/sites/fields'

type Selection = { kind: 'site'; id: string } | { kind: 'vertical'; key: string } | { kind: 'new-site'; vertical?: string | null } | { kind: 'new-vertical' } | null

export default function SiteProfilesPage() {
  const [sel, setSel] = useState<Selection>(null)
  const { data, isLoading } = useQuery<SiteProfiles>({
    queryKey: ['site-profiles'],
    queryFn: async () => (await siteProfilesApi.list()).data,
  })
  const verticals = data?.verticals ?? []
  const sites = data?.sites ?? []
  const noVertical = sites.filter((s) => !s.vertical || !verticals.some((v) => v.key === s.vertical))

  const rowCls = (on: boolean) =>
    `w-full flex items-center gap-2 px-3 py-1.5 rounded-[var(--radius-md)] text-left border-none cursor-pointer text-[13px] ${on ? 'bg-surface-active text-content-primary' : 'bg-transparent text-content-secondary hover:bg-surface-hover'}`

  const siteRows = (list: typeof sites) =>
    list.map((s) => (
      <button key={s.id} onClick={() => setSel({ kind: 'site', id: s.id })} className={`${rowCls(sel?.kind === 'site' && sel.id === s.id)} pl-6`}>
        <span className="truncate flex-1">{s.name}</span>
        <StatusBadge site={s} />
      </button>
    ))

  let editor: React.ReactNode = (
    <p className={T.itemDesc}>왼쪽에서 분야나 사이트를 고르거나 새로 추가하세요. 분야는 같은 분야의 모든 사이트가 공유하는 지침이고, 사이트는 그 사이트에서만 맞는 특성입니다.</p>
  )
  if (sel?.kind === 'site') {
    const s = sites.find((x) => x.id === sel.id)
    if (s) editor = <SiteEditor key={`${s.id}:${s.version}`} site={s} verticals={verticals} onSaved={(id) => setSel({ kind: 'site', id })} onDeleted={() => setSel(null)} />
  } else if (sel?.kind === 'vertical') {
    const v = verticals.find((x) => x.key === sel.key)
    if (v) editor = <VerticalEditor key={`${v.key}:${v.version}`} vertical={v} onSaved={(key) => setSel({ kind: 'vertical', key })} onDeleted={() => setSel(null)} />
  } else if (sel?.kind === 'new-site') {
    editor = <SiteEditor key={`new-site:${sel.vertical ?? ''}`} site={null} verticals={verticals} defaultVertical={sel.vertical} onSaved={(id) => setSel({ kind: 'site', id })} onDeleted={() => setSel(null)} />
  } else if (sel?.kind === 'new-vertical') {
    editor = <VerticalEditor key="new-vertical" vertical={null} onSaved={(key) => setSel({ kind: 'vertical', key })} onDeleted={() => setSel(null)} />
  }

  return (
    <SettingsPage
      active="sites"
      title="웹사이트 분석"
      subtitle="브라우저 에이전트가 사이트에서 일할 때 받는 분야 공통 지침과 사이트별 특성을 관리합니다. 모든 사용자가 함께 쓰고 편집합니다."
    >
      <div className="flex flex-col lg:flex-row gap-6 items-start">
        <aside className="w-full lg:w-[300px] flex-shrink-0 space-y-3 lg:sticky lg:top-0 lg:max-h-[calc(100vh-150px)] lg:overflow-y-auto">
          <div className="flex gap-2">
            <button onClick={() => setSel({ kind: 'new-site' })} className={`${secondaryBtn} flex items-center gap-1`}><Plus size={14} />사이트</button>
            <button onClick={() => setSel({ kind: 'new-vertical' })} className={`${secondaryBtn} flex items-center gap-1`}><Plus size={14} />분야</button>
          </div>
          {isLoading && <p className={T.itemDesc}>불러오는 중…</p>}
          {verticals.map((v) => (
            <div key={v.key} className="space-y-0.5">
              <button onClick={() => setSel({ kind: 'vertical', key: v.key })} className={rowCls(sel?.kind === 'vertical' && sel.key === v.key)}>
                <span className="truncate flex-1 font-medium text-content-primary">{v.name}</span>
                <span className="text-xs text-content-tertiary">{v.site_count}</span>
              </button>
              {siteRows(sites.filter((s) => s.vertical === v.key))}
              <button onClick={() => setSel({ kind: 'new-site', vertical: v.key })} className="pl-6 pr-3 py-1 text-xs text-content-tertiary hover:text-content-primary border-none bg-transparent cursor-pointer text-left">
                + 이 분야에 사이트 추가
              </button>
            </div>
          ))}
          {noVertical.length > 0 && (
            <div className="space-y-0.5">
              <div className="px-3 py-1.5 text-[13px] font-medium text-content-primary">분야 없음</div>
              {siteRows(noVertical)}
            </div>
          )}
          {data && <p className="text-xs text-content-tertiary px-1">확인한 지 {data.stale_days}일이 지나면 ‘오래됨’으로 표시합니다. 오래된 요령도 에이전트에게는 계속 제공됩니다.</p>}
        </aside>
        <section className="w-full lg:flex-1 min-w-0 max-w-[760px]">{editor}</section>
      </div>
    </SettingsPage>
  )
}

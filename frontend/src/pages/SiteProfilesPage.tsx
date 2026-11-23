import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, Plus, X } from 'lucide-react'
import { siteProfilesApi, type SiteProfiles } from '../api/siteProfiles'
import SettingsPage from '../components/skills/SettingsPage'
import { T } from '../components/skills/typography'
import SiteEditor from '../components/sites/SiteEditor'
import VerticalEditor from '../components/sites/VerticalEditor'
import StatusBadge from '../components/sites/StatusBadge'
import { secondaryBtn } from '../components/sites/fields'

type Selection = { kind: 'site'; id: string } | { kind: 'vertical'; key: string } | { kind: 'new-site'; vertical?: string | null; category?: string | null } | { kind: 'new-vertical'; category?: string | null } | null

export default function SiteProfilesPage() {
  const [sel, setSel] = useState<Selection>(null)
  const [open, setOpen] = useState<Record<string, boolean>>({}) // 분야별 펼침 (기본: 접힘)
  const { data, isLoading } = useQuery<SiteProfiles>({
    queryKey: ['site-profiles'],
    queryFn: async () => (await siteProfilesApi.list()).data,
  })
  const categories = data?.categories ?? []
  const verticals = data?.verticals ?? []
  const sites = data?.sites ?? []
  const noVertical = sites.filter((s) => !s.vertical || !verticals.some((v) => v.key === s.vertical))
  const known = (c: string | null) => !!c && categories.some((x) => x.key === c)
  const vertsIn = (cat: string) => verticals.filter((v) => (known(v.category) ? v.category : '') === cat)
  const looseIn = (cat: string) => noVertical.filter((s) => (known(s.category) ? s.category : '') === cat) // 분야 없이 카테고리에 바로 속한 사이트
  const catCount = (cat: string) => vertsIn(cat).reduce((n, v) => n + v.site_count, 0) + looseIn(cat).length

  const selCategory = (() => {
    if (sel?.kind === 'vertical') return verticals.find((v) => v.key === sel.key)?.category ?? ''
    if (sel?.kind === 'site') { const s = sites.find((x) => x.id === sel.id); return (s?.vertical ? verticals.find((v) => v.key === s.vertical)?.category : s?.category) ?? '' }
    return null
  })()
  const catOpen = (cat: string) => open[`c:${cat}`] ?? true // 카테고리는 처음부터 펼쳐 분야 목록이 보이게 한다 (분야는 접힌 채)
  const toggleCat = (cat: string) => setOpen((o) => ({ ...o, [`c:${cat}`]: !catOpen(cat) }))
  const selVertical = sel?.kind === 'vertical' ? sel.key : sel?.kind === 'site' ? sites.find((x) => x.id === sel.id)?.vertical : sel?.kind === 'new-site' ? sel.vertical : null
  const isOpen = (key: string) => open[key] ?? selVertical === key // 고른 항목이 속한 분야는 처음부터 펼쳐 둔다
  const toggle = (key: string) => setOpen((o) => ({ ...o, [key]: !isOpen(key) }))

  const off = (key: string) => sites.filter((s) => s.vertical === key && !s.enabled).length
  const rowCls = (on: boolean) =>
    `w-full flex items-center gap-2 px-3 py-1.5 rounded-[var(--radius-md)] text-left border-none cursor-pointer text-[13px] ${on ? 'bg-surface-active text-content-primary' : 'bg-transparent text-content-secondary hover:bg-surface-hover'}`

  const siteRows = (list: typeof sites) =>
    list.map((s) => (
      <button key={s.id} onClick={() => setSel({ kind: 'site', id: s.id })} className={`${rowCls(sel?.kind === 'site' && sel.id === s.id)} pl-6`}>
        <span className={`truncate flex-1 ${s.enabled ? '' : 'line-through opacity-60'}`} title={s.enabled ? undefined : '사용 안 함: 에이전트가 이 사이트에 접속하지 않습니다'}>{s.name}</span>
        <StatusBadge site={s} />
      </button>
    ))

  const verticalBlock = (v: (typeof verticals)[number]) => (
            <div key={v.key} className="space-y-0.5">
              <button onClick={() => { setSel({ kind: 'vertical', key: v.key }); setOpen((o) => ({ ...o, [v.key]: true })) }} className={rowCls(sel?.kind === 'vertical' && sel.key === v.key)}>
                <span
                  role="button"
                  aria-label={isOpen(v.key) ? '접기' : '펼치기'}
                  aria-expanded={isOpen(v.key)}
                  onClick={(e) => { e.stopPropagation(); toggle(v.key) }}
                  className="flex-shrink-0 text-content-tertiary hover:text-content-primary"
                >
                  {isOpen(v.key) ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </span>
                <span className="truncate flex-1 font-medium text-content-primary">{v.name}</span>
                <span className="text-xs text-content-tertiary" title={off(v.key) ? `사용 안 함 ${off(v.key)}개 포함` : undefined}>
                  {v.site_count}{off(v.key) > 0 && <span className="text-red-500"> (끔 {off(v.key)})</span>}
                </span>
              </button>
              {isOpen(v.key) && (
                <>
                  {siteRows(sites.filter((s) => s.vertical === v.key))}
                  <button onClick={() => setSel({ kind: 'new-site', vertical: v.key })} className="pl-6 pr-3 py-1 text-xs text-content-tertiary hover:text-content-primary border-none bg-transparent cursor-pointer text-left">
                    + 이 분야에 사이트 추가
                  </button>
                </>
              )}
            </div>
          )

  let modal: React.ReactNode = null
  let editor: React.ReactNode = (
    <p className={T.itemDesc}>왼쪽에서 분야나 사이트를 고르거나 새로 추가하세요. 분야는 같은 분야의 모든 사이트가 공유하는 지침이고, 사이트는 그 사이트에서만 맞는 특성입니다.</p>
  )
  if (sel?.kind === 'site') {
    const s = sites.find((x) => x.id === sel.id)
    if (s) editor = <SiteEditor key={`${s.id}:${s.version}`} site={s} verticals={verticals} categories={categories} onSaved={(id) => setSel({ kind: 'site', id })} onDeleted={() => setSel(null)} />
  } else if (sel?.kind === 'vertical') {
    const v = verticals.find((x) => x.key === sel.key)
    if (v) editor = <VerticalEditor key={`${v.key}:${v.version}`} vertical={v} categories={categories} onSaved={(key) => setSel({ kind: 'vertical', key })} onDeleted={() => setSel(null)} />
  } else if (sel?.kind === 'new-site') {
    modal = <SiteEditor key={`new-site:${sel.vertical ?? ''}:${sel.category ?? ''}`} site={null} verticals={verticals} categories={categories} defaultVertical={sel.vertical} defaultCategory={sel.category} onSaved={(id) => setSel({ kind: 'site', id })} onDeleted={() => setSel(null)} />
  } else if (sel?.kind === 'new-vertical') {
    modal = <VerticalEditor key={`new-vertical:${sel.category ?? ''}`} vertical={null} categories={categories} defaultCategory={sel.category} onSaved={(key) => setSel({ kind: 'vertical', key })} onDeleted={() => setSel(null)} />
  }

  // 새로 등록하는 화면은 팝업으로 띄운다 (Esc·바깥 클릭·닫기 버튼으로 닫음)
  const closeModal = () => setSel(null)
  useEffect(() => {
    if (!modal) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setSel(null) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [!!modal]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <SettingsPage
      active="sites"
      title="웹사이트 분석"
      subtitle="브라우저 에이전트가 사이트에서 일할 때 받는 분야 공통 지침과 사이트별 특성을 관리합니다. 모든 사용자가 함께 쓰고 편집합니다."
    >
      <div className="flex flex-col lg:flex-row gap-6 items-start">
        <aside className="w-full lg:w-[300px] flex-shrink-0 space-y-3 lg:sticky lg:top-0 lg:max-h-[calc(100vh-150px)] lg:overflow-y-auto">
          <div className="flex gap-2">
            <button onClick={() => setSel({ kind: 'new-vertical' })} className={`${secondaryBtn} flex items-center gap-1`}><Plus size={14} />분야</button>
            <button onClick={() => setSel({ kind: 'new-site' })} className={`${secondaryBtn} flex items-center gap-1`}><Plus size={14} />사이트</button>
          </div>
          {isLoading && <p className={T.itemDesc}>불러오는 중…</p>}
          {categories.map((c) => (
            <div key={c.key} className="space-y-0.5">
              <button onClick={() => toggleCat(c.key)} aria-expanded={catOpen(c.key)} className={`${rowCls(false)} font-semibold`}>
                {catOpen(c.key) ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                <span className="truncate flex-1 text-content-primary">{c.name}</span>
                <span className="text-xs text-content-tertiary">{catCount(c.key)}</span>
              </button>
              {catOpen(c.key) && (
                <div className="ml-3 pl-1 border-l border-border space-y-0.5">
                  {vertsIn(c.key).map(verticalBlock)}
                  {siteRows(looseIn(c.key))}
                  {vertsIn(c.key).length === 0 && looseIn(c.key).length === 0 && <p className="px-3 py-1 text-xs text-content-tertiary">등록된 분야·사이트가 없습니다</p>}
                  <button onClick={() => setSel({ kind: 'new-vertical', category: c.key })} className="px-3 py-1 text-xs text-content-tertiary hover:text-content-primary border-none bg-transparent cursor-pointer text-left">
                    + 이 카테고리에 분야 추가
                  </button>
                </div>
              )}
            </div>
          ))}
          {(vertsIn('').length > 0 || looseIn('').length > 0) && (
            <div className="space-y-0.5">
              <button onClick={() => toggleCat('')} aria-expanded={catOpen('')} className={`${rowCls(false)} font-semibold`}>
                {catOpen('') ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                <span className="truncate flex-1 text-content-primary">카테고리 없음</span>
                <span className="text-xs text-content-tertiary">{catCount('')}</span>
              </button>
              {catOpen('') && <div className="ml-3 pl-1 border-l border-border space-y-0.5">{vertsIn('').map(verticalBlock)}{siteRows(looseIn(''))}</div>}
            </div>
          )}
          {data && <p className="text-xs text-content-tertiary px-1">확인한 지 {data.stale_days}일이 지나면 ‘오래됨’으로 표시합니다. 오래된 요령도 에이전트에게는 계속 제공됩니다.</p>}
        </aside>
        <section className="w-full lg:flex-1 min-w-0 max-w-[760px]">{editor}</section>
      </div>
      {modal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onMouseDown={(e) => { if (e.target === e.currentTarget) closeModal() }}>
          <div role="dialog" aria-modal="true" className="relative bg-surface-primary border border-border rounded-xl shadow-xl w-full max-w-[820px] max-h-[90vh] overflow-y-auto p-6">
            <button onClick={closeModal} aria-label="닫기" title="닫기" className="absolute right-3 top-3 p-1.5 text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer"><X size={16} /></button>
            {modal}
          </div>
        </div>
      )}
    </SettingsPage>
  )
}

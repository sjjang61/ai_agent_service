import type { SiteProfile } from '../../api/siteProfiles'

/** 상태 배지: 꺼짐 > 초안 > 오래됨 > 검증됨 순으로 하나만 보여 준다. */
export function siteBadge(s: Pick<SiteProfile, 'status' | 'enabled' | 'is_stale'>): { label: string; cls: string } {
  if (!s.enabled) return { label: '꺼짐', cls: 'bg-surface-active text-content-tertiary' }
  if (s.status === 'draft') return { label: '초안', cls: 'bg-surface-active text-content-secondary' }
  if (s.is_stale || s.status === 'stale') return { label: '오래됨', cls: 'bg-amber-500/15 text-amber-600' }
  return { label: '검증됨', cls: 'bg-green-500/15 text-green-600' }
}

export default function StatusBadge({ site }: { site: Pick<SiteProfile, 'status' | 'enabled' | 'is_stale'> }) {
  const b = siteBadge(site)
  return <span className={`px-1.5 py-0.5 rounded-full text-[11px] font-medium flex-shrink-0 ${b.cls}`}>{b.label}</span>
}

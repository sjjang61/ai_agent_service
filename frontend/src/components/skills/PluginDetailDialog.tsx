import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { skillsApi } from '../../api/skills'
import { formatFullDateTime } from '../../utils/time'
import type { Plugin, Skill } from '../../types/skill'
import { SkillBrowser } from './SkillDetailDialog'

/** 플러그인 상세: 메타 정보와 포함된 스킬(각 스킬의 파일 보기·한글 번역은 스킬 상세와 같다) */
export default function PluginDetailDialog({ plugin, onClose }: { plugin: Plugin; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const { data: all = [], isLoading } = useQuery<Skill[]>({
    queryKey: ['skills'],
    queryFn: async () => (await skillsApi.list()).data,
  })
  const skills = all.filter((s) => s.plugin_id === plugin.id || plugin.skill_names.includes(s.name))
  const [selId, setSelId] = useState<string | null>(null)
  const selected = skills.find((s) => s.id === selId) ?? skills[0]

  const source = plugin.source_url.startsWith('upload:') ? `ZIP 업로드 (${plugin.source_url.slice(7)})` : plugin.source_url

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onMouseDown={onClose}>
      <div
        className="w-full max-w-[980px] h-[min(760px,92vh)] flex flex-col bg-surface-primary border border-border rounded-[var(--radius-xl)] shadow-xl overflow-hidden"
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={`${plugin.name} 상세`}
      >
        <div className="flex items-start gap-3 px-6 pt-5 pb-3 border-b border-border">
          <div className="min-w-0 flex-1">
            <h2 className="text-[17px] font-semibold text-content-primary truncate">
              {plugin.name}
              {plugin.version && <span className="ml-2 text-xs font-normal text-content-tertiary">v{plugin.version}</span>}
            </h2>
            {plugin.description && <p className="mt-1 text-[13px] text-content-secondary">{plugin.description}</p>}
            <p className="mt-2 text-xs text-content-muted break-all">
              {plugin.is_active ? '사용 중' : '비활성'}
              {' · 출처 '}
              {source.startsWith('http') ? <a href={source} target="_blank" rel="noopener noreferrer" className="text-accent-primary">{source}</a> : source}
              {' · 설치 '}{formatFullDateTime(plugin.created_at)}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-content-muted mr-1">스킬 {plugin.skill_names.length}개</span>
              {skills.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setSelId(s.id)}
                  title={s.description ?? ''}
                  className={`px-3 py-1 rounded-full text-xs border cursor-pointer transition-colors ${selected?.id === s.id ? 'bg-accent-primary border-accent-primary text-white' : 'bg-transparent border-border text-content-secondary hover:text-content-primary hover:bg-surface-hover'}`}
                >
                  {s.name}
                </button>
              ))}
            </div>
          </div>
          <button onClick={onClose} aria-label="닫기" className="text-content-tertiary hover:text-content-primary border-none bg-transparent cursor-pointer">
            <X size={18} />
          </button>
        </div>

        {isLoading ? (
          <div className="flex-1 flex items-center justify-center text-sm text-content-muted">불러오는 중...</div>
        ) : selected ? (
          <>
            {selected.description && <div className="px-6 py-2 text-xs text-content-secondary border-b border-border">{selected.name}: {selected.description}</div>}
            <SkillBrowser key={selected.id} skill={selected} />
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-sm text-content-muted">이 플러그인에 연결된 스킬을 찾을 수 없습니다.</div>
        )}
      </div>
    </div>
  )
}

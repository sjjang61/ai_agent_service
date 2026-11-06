import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDownAZ, ArrowUpAZ, ChevronLeft, ChevronRight, ExternalLink, Loader2, Puzzle, X, Zap } from 'lucide-react'
import { Link } from 'react-router-dom'
import { skillsApi } from '../../api/skills'
import { errorText } from '../skills/common'
import type { SandboxSkillList } from '../../types/skill'

const PAGE = 4

function Switch({ on, busy, onChange, label }: { on: boolean; busy: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={busy}
      onClick={() => onChange(!on)}
      className={`relative flex-shrink-0 w-9 h-5 rounded-full border-none cursor-pointer transition-colors disabled:cursor-wait ${on ? 'bg-accent-primary' : 'bg-surface-active'}`}
    >
      {busy ? (
        <Loader2 size={12} className="absolute top-1 left-1/2 -ml-1.5 animate-spin text-white" />
      ) : (
        <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${on ? 'translate-x-4' : ''}`} />
      )}
    </button>
  )
}

/**
 * 스킬 저장소: custom 스킬 목록. 켜져 있는 스킬은 현재 sandbox 에 설치(로드)된 것이다.
 * 끈 스킬을 켜면 현재 sandbox 에 동적으로 설치하고(꺼져 있으면 sandbox 를 시작·복구), 끄면 현재 sandbox 에서 제거한다.
 */
export default function SkillPickerDialog({ conversationId, onClose }: { conversationId: string; onClose: () => void }) {
  const qc = useQueryClient()
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<'all' | 'loaded' | 'unloaded'>('all')
  const [asc, setAsc] = useState(true)
  const [page, setPage] = useState(0)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const key = ['sandbox-skills', conversationId]
  const { data, isLoading, isError } = useQuery<SandboxSkillList>({
    queryKey: key,
    queryFn: async () => (await skillsApi.sandboxList(conversationId)).data,
    refetchOnWindowFocus: false,
  })

  const toggle = async (id: string, installed: boolean) => {
    setBusyId(id)
    setError('')
    try {
      await skillsApi.setInSandbox(id, installed, conversationId)
      await qc.invalidateQueries({ queryKey: key })
      qc.invalidateQueries({ queryKey: ['sandbox-artifacts'] }) // 산출물 목록(/workspace/skills)이 바뀐다
    } catch (e) {
      setError(errorText(e, installed ? '스킬을 sandbox 에 설치하지 못했습니다' : '스킬을 sandbox 에서 제거하지 못했습니다'))
    } finally {
      setBusyId(null)
    }
  }

  const q = query.trim().toLowerCase()
  const all = data?.skills ?? []
  const filtered = all
    .filter((s) => (filter === 'loaded' ? s.installed : filter === 'unloaded' ? !s.installed : true))
    .filter((s) => !q || s.name.toLowerCase().includes(q) || (s.description ?? '').toLowerCase().includes(q))
    .sort((a, b) => (asc ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name)))
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE))
  const cur = Math.min(page, pages - 1)
  const shown = filtered.slice(cur * PAGE, cur * PAGE + PAGE)
  const loadedCount = all.filter((s) => s.installed).length

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onMouseDown={onClose}>
      <div
        className="w-full max-w-[640px] max-h-[88vh] flex flex-col bg-surface-primary border border-border rounded-[var(--radius-xl)] shadow-xl overflow-hidden"
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="스킬 저장소"
      >
        <div className="flex items-center gap-3 px-6 pt-5 pb-3">
          <span className="w-9 h-9 rounded-lg bg-surface-tertiary flex items-center justify-center"><Puzzle size={18} className="text-content-primary" /></span>
          <h2 className="text-[16px] font-semibold text-content-primary">스킬 저장소</h2>
          <Link to="/skills" title="스킬 메뉴에서 관리" onClick={onClose} className="text-content-tertiary hover:text-content-primary"><ExternalLink size={15} /></Link>
          <div className="flex-1" />
          <button onClick={onClose} aria-label="닫기" className="text-content-tertiary hover:text-content-primary border-none bg-transparent cursor-pointer"><X size={18} /></button>
        </div>

        <div className="flex items-center gap-2 px-6 pb-3">
          <input
            autoFocus
            value={query}
            onChange={(e) => { setQuery(e.target.value); setPage(0) }}
            placeholder="스킬 검색..."
            className="flex-1 min-w-0 px-3 py-2 bg-surface-secondary border border-border rounded-lg text-sm text-content-primary placeholder-content-muted focus:outline-none focus:border-accent-primary"
          />
          <select
            value={filter}
            onChange={(e) => { setFilter(e.target.value as typeof filter); setPage(0) }}
            className="px-3 py-2 bg-surface-secondary border border-border rounded-lg text-sm text-content-primary"
            aria-label="필터"
          >
            <option value="all">전체</option>
            <option value="loaded">로드됨</option>
            <option value="unloaded">미로드</option>
          </select>
          <button
            onClick={() => setAsc((a) => !a)}
            title={asc ? '이름 오름차순' : '이름 내림차순'}
            aria-label="정렬"
            className="px-2.5 py-2 bg-surface-secondary border border-border rounded-lg text-content-secondary hover:text-content-primary cursor-pointer"
          >
            {asc ? <ArrowDownAZ size={16} /> : <ArrowUpAZ size={16} />}
          </button>
        </div>

        <p className="px-6 pb-2 text-xs text-content-muted">
          custom 스킬은 자동 설치되지 않습니다. 켜면 현재 sandbox 에 설치하고(꺼져 있으면 시작·복구), 끄면 제거합니다.
          {data && ` 현재 ${loadedCount}개 로드됨${data.sandbox_running ? '' : ' · sandbox 가 꺼져 있음'}`}
        </p>
        {error && <p className="px-6 pb-2 text-xs text-accent-red">{error}</p>}

        <div className="flex-1 overflow-y-auto px-6 pb-3 space-y-3 min-h-[200px]">
          {isLoading ? (
            <p className="py-10 text-center text-xs text-content-muted">불러오는 중...</p>
          ) : isError ? (
            <p className="py-10 text-center text-xs text-accent-red">스킬 목록을 불러오지 못했습니다</p>
          ) : all.length === 0 ? (
            <p className="py-10 text-center text-xs text-content-muted">custom 타입 스킬이 없습니다. 스킬 메뉴에서 스킬의 타입을 '커스텀'으로 바꾸거나 새 스킬을 커스텀으로 추가하세요.</p>
          ) : shown.length === 0 ? (
            <p className="py-10 text-center text-xs text-content-muted">조건에 맞는 스킬이 없습니다.</p>
          ) : (
            shown.map((s) => (
              <div key={s.id} className={`rounded-xl border bg-surface-primary ${s.installed ? 'border-accent-primary/50' : 'border-border'}`}>
                <div className="flex items-center gap-2.5 px-3 py-2.5">
                  <span className="w-7 h-7 rounded-md bg-surface-tertiary flex items-center justify-center flex-shrink-0"><Zap size={14} className={s.installed ? 'text-accent-primary' : 'text-content-muted'} /></span>
                  <span className="text-sm font-medium text-content-primary truncate" title={s.name}>{s.name}</span>
                  <span className="px-2 py-0.5 rounded-full text-[11px] border border-accent-green/40 text-accent-green bg-accent-green/10 flex-shrink-0">Custom</span>
                  {s.installed && <span className="text-[11px] text-accent-primary flex-shrink-0">로드됨</span>}
                  <div className="flex-1" />
                  <Switch on={s.installed} busy={busyId === s.id} label={`${s.name} ${s.installed ? '제거' : '설치'}`} onChange={(v) => toggle(s.id, v)} />
                </div>
                <div className="px-3 py-2.5 border-t border-border">
                  <div className="text-[10px] tracking-wider text-content-muted mb-1">DESCRIPTION</div>
                  <p className="text-[13px] text-content-secondary line-clamp-3">{s.description || '설명 없음'}</p>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="flex items-center px-6 py-3 border-t border-border text-xs text-content-muted">
          <span>{filtered.length === 0 ? 'Showing 0 of 0' : `Showing ${cur * PAGE + 1}-${Math.min((cur + 1) * PAGE, filtered.length)} of ${filtered.length}`}</span>
          <div className="flex-1" />
          <button disabled={cur === 0} onClick={() => setPage(cur - 1)} aria-label="이전" className="p-1.5 border-none bg-transparent cursor-pointer text-content-secondary disabled:opacity-30 disabled:cursor-default"><ChevronLeft size={16} /></button>
          <button disabled={cur >= pages - 1} onClick={() => setPage(cur + 1)} aria-label="다음" className="p-1.5 border-none bg-transparent cursor-pointer text-content-secondary disabled:opacity-30 disabled:cursor-default"><ChevronRight size={16} /></button>
        </div>
      </div>
    </div>
  )
}

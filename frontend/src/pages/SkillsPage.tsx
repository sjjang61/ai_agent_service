import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import CustomizeLayout from '../components/skills/CustomizeLayout'
import { T } from '../components/skills/typography'
import PageHeader from '../components/skills/PageHeader'
import AddSkillDialog from '../components/skills/AddSkillDialog'
import { GithubDialog, ItemCard, errorText } from '../components/skills/common'
import { skillsApi } from '../api/skills'
import type { Skill, SkillCreateInput } from '../types/skill'

const PAGE = 12

export default function SkillsPage() {
  const queryClient = useQueryClient()
  const { data: skills = [], isLoading, isFetching, refetch } = useQuery<Skill[]>({
    queryKey: ['skills'],
    queryFn: async () => (await skillsApi.list()).data,
  })
  const [query, setQuery] = useState('')
  const [source, setSource] = useState<'all' | 'personal' | string>('all') // string = plugin_id
  const [dialog, setDialog] = useState<'github' | 'custom' | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [notice, setNotice] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null)

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['skills'] })

  const plugins = useMemo(() => {
    const m = new Map<string, string>()
    skills.forEach((s) => s.plugin_id && m.set(s.plugin_id, s.plugin_name ?? s.plugin_id))
    return [...m.entries()].map(([id, name]) => ({ id, name }))
  }, [skills])

  const q = query.trim().toLowerCase()
  const visible = skills.filter((s) => {
    if (source === 'personal' && s.plugin_id) return false
    if (source !== 'all' && source !== 'personal' && s.plugin_id !== source) return false
    return !q || s.name.toLowerCase().includes(q) || (s.description ?? '').toLowerCase().includes(q)
  })
  const shown = expanded ? visible : visible.slice(0, PAGE)

  const syncNote = (synced: boolean, err: string | null | undefined, okText: string) =>
    setNotice(synced ? { kind: 'ok', text: `${okText} (sandbox /workspace/skills/ 에 복사됨)` } : { kind: 'err', text: `${okText} — sandbox 복사 실패: ${err ?? '알 수 없는 오류'}` })

  const installGithub = async (url: string) => {
    const res = await skillsApi.install(url)
    refresh()
    syncNote(res.data.sandbox_synced, res.data.sandbox_error, `설치됨: ${(res.data.installed as Skill[]).map((s) => s.name).join(', ')}`)
    return ''
  }

  const create = async (input: SkillCreateInput) => {
    const res = await skillsApi.create(input)
    refresh()
    syncNote(res.data.sandbox_synced, res.data.sandbox_error, `추가됨: ${res.data.installed[0].name}`)
  }

  const toggle = async (s: Skill) => {
    try {
      await skillsApi.setActive(s.id, !s.is_active)
      refresh()
    } catch (err) {
      setNotice({ kind: 'err', text: errorText(err, '상태를 바꾸지 못했습니다') })
    }
  }

  const remove = async (s: Skill) => {
    if (!confirm(`'${s.name}' 스킬을 삭제할까요?`)) return
    try {
      await skillsApi.remove(s.id)
      refresh()
    } catch (err) {
      setNotice({ kind: 'err', text: errorText(err, '삭제하지 못했습니다') })
    }
  }

  const resync = async () => {
    try {
      const res = await skillsApi.sync()
      setNotice(res.data.sandbox_error ? { kind: 'err', text: `Sandbox 동기화 실패: ${res.data.sandbox_error}` } : { kind: 'ok', text: `${res.data.synced}개 스킬을 sandbox 로 다시 복사했습니다` })
    } catch {
      setNotice({ kind: 'err', text: 'Sandbox 동기화 실패' })
    }
  }

  const chip = (active: boolean) =>
    `px-4 py-2 rounded-full text-[13px] border-none cursor-pointer transition-colors ${active ? 'bg-surface-active text-content-primary' : 'bg-transparent text-content-secondary hover:bg-surface-hover'}`

  return (
    <CustomizeLayout active="skills" installed={skills} onPickInstalled={(n) => { setQuery(n); setSource('all') }}>
      <PageHeader
        title="스킬"
        subtitle="작업별 스킬로 에이전트 확장"
        query={query}
        onQuery={setQuery}
        placeholder="스킬 검색"
        onRefresh={() => refetch()}
        refreshing={isFetching}
        onSettings={{ title: '설치된 스킬을 sandbox 로 다시 복사', run: resync }}
        addItems={[
          { label: 'GitHub 에서 추가', hint: '저장소/폴더 URL 로 설치', onClick: () => setDialog('github') },
          { label: '직접 추가', hint: 'SKILL.md 를 작성하거나 파일로 불러오기', onClick: () => setDialog('custom') },
        ]}
      />

      <div className="flex-1 overflow-y-auto px-8 pb-10">
        {notice && (
          <div className={`mb-4 px-4 py-2.5 rounded-[var(--radius-md)] text-[13px] border ${notice.kind === 'ok' ? 'text-accent-green border-accent-green/30' : 'text-accent-red border-accent-red/30'}`}>
            {notice.text}
          </div>
        )}

        <div className="flex items-center gap-2 border-b border-border pb-3 mb-2">
          <h2 className={`${T.section} px-3 mr-2`}>설치됨 <span className="text-[13px] font-normal text-content-tertiary">{visible.length}</span></h2>
          <button className={chip(source === 'all')} onClick={() => setSource('all')}>전체</button>
          <button className={chip(source === 'personal')} onClick={() => setSource('personal')}>개인</button>
          {plugins.map((p) => (
            <button key={p.id} className={chip(source === p.id)} onClick={() => setSource(p.id)} title="플러그인">
              {p.name}
            </button>
          ))}
        </div>

        {isLoading ? (
          <div className="text-content-tertiary text-sm py-12 text-center">불러오는 중...</div>
        ) : visible.length === 0 ? (
          <div className="text-content-muted text-sm py-12 text-center">
            {skills.length === 0 ? '설치된 스킬이 없습니다. 오른쪽 위 “추가” 로 GitHub 에서 설치하거나 직접 만들 수 있습니다.' : '조건에 맞는 스킬이 없습니다.'}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-x-6">
              {shown.map((s) => (
                <ItemCard
                  key={s.id}
                  name={s.name}
                  description={s.description}
                  meta={s.plugin_name ? `플러그인 · ${s.plugin_name}` : undefined}
                  active={s.is_active}
                  onToggle={() => toggle(s)}
                  onDelete={() => remove(s)}
                />
              ))}
            </div>
            {visible.length > PAGE && (
              <button onClick={() => setExpanded((e) => !e)} className="mt-3 ml-3 text-[13px] text-content-tertiary hover:text-content-primary border-none bg-transparent cursor-pointer">
                {expanded ? '접기' : `외 ${visible.length - PAGE}개 더 보기`}
              </button>
            )}
          </>
        )}
      </div>

      {dialog === 'github' && (
        <GithubDialog
          title="GitHub 에서 스킬 추가"
          hint="SKILL.md 가 있는 저장소 또는 폴더의 URL 을 입력하세요. 하위 폴더에 있는 여러 스킬도 한 번에 설치됩니다."
          placeholder="https://github.com/owner/repo/tree/main/skills/my-skill"
          onInstall={installGithub}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog === 'custom' && <AddSkillDialog onCreate={create} onClose={() => setDialog(null)} />}
    </CustomizeLayout>
  )
}

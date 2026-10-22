import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import CustomizeLayout from '../components/skills/CustomizeLayout'
import PageHeader from '../components/skills/PageHeader'
import { GithubDialog, ItemCard, errorText } from '../components/skills/common'
import { skillsApi } from '../api/skills'
import type { Plugin } from '../types/skill'

export default function PluginsPage() {
  const queryClient = useQueryClient()
  const { data: plugins = [], isLoading, isFetching, refetch } = useQuery<Plugin[]>({
    queryKey: ['plugins'],
    queryFn: async () => (await skillsApi.listPlugins()).data,
  })
  const [query, setQuery] = useState('')
  const [dialog, setDialog] = useState(false)
  const [notice, setNotice] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null)

  // 플러그인 변경은 skill 목록(활성 상태/소속)에도 영향을 준다
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['plugins'] })
    queryClient.invalidateQueries({ queryKey: ['skills'] })
  }

  const q = query.trim().toLowerCase()
  const visible = plugins.filter((p) => !q || p.name.toLowerCase().includes(q) || (p.description ?? '').toLowerCase().includes(q))

  const install = async (url: string) => {
    const res = await skillsApi.installPlugin(url)
    refresh()
    const names = (res.data.installed as Plugin[]).map((p) => p.name).join(', ')
    const base = `설치됨: ${names} (스킬 ${res.data.skills.length}개)`
    setNotice(res.data.sandbox_synced ? { kind: 'ok', text: base } : { kind: 'err', text: `${base} — sandbox 복사 실패: ${res.data.sandbox_error ?? '알 수 없는 오류'}` })
    return ''
  }

  const toggle = async (p: Plugin) => {
    try {
      await skillsApi.setPluginActive(p.id, !p.is_active)
      refresh()
    } catch (err) {
      setNotice({ kind: 'err', text: errorText(err, '상태를 바꾸지 못했습니다') })
    }
  }

  const remove = async (p: Plugin) => {
    if (!confirm(`'${p.name}' 플러그인과 포함된 스킬 ${p.skill_names.length}개를 삭제할까요?`)) return
    try {
      await skillsApi.removePlugin(p.id)
      refresh()
    } catch (err) {
      setNotice({ kind: 'err', text: errorText(err, '삭제하지 못했습니다') })
    }
  }

  return (
    <CustomizeLayout active="plugins" installed={plugins} onPickInstalled={setQuery}>
      <PageHeader
        title="플러그인"
        subtitle="여러 스킬을 묶은 패키지로 에이전트 확장"
        query={query}
        onQuery={setQuery}
        placeholder="플러그인 검색"
        onRefresh={() => refetch()}
        refreshing={isFetching}
        addItems={[{ label: 'GitHub 에서 추가', hint: 'plugin.json 또는 marketplace.json 이 있는 저장소', onClick: () => setDialog(true) }]}
      />
      <div className="flex-1 overflow-y-auto px-8 pb-10">
        {notice && (
          <div className={`mb-4 px-4 py-2.5 rounded-[var(--radius-md)] text-[13px] border ${notice.kind === 'ok' ? 'text-accent-green border-accent-green/30' : 'text-accent-red border-accent-red/30'}`}>
            {notice.text}
          </div>
        )}
        <div className="border-b border-border pb-3 mb-2">
          <h2 className="text-[17px] font-semibold text-content-primary px-3">설치됨 <span className="text-[13px] font-normal text-content-tertiary">{visible.length}</span></h2>
        </div>
        {isLoading ? (
          <div className="text-content-tertiary text-sm py-12 text-center">불러오는 중...</div>
        ) : visible.length === 0 ? (
          <div className="text-content-muted text-sm py-12 text-center">
            {plugins.length === 0 ? '설치된 플러그인이 없습니다. 오른쪽 위 “추가” 로 GitHub 저장소에서 설치하세요.' : '조건에 맞는 플러그인이 없습니다.'}
          </div>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-x-6">
            {visible.map((p) => (
              <ItemCard
                key={p.id}
                name={p.name}
                description={p.description || `스킬 ${p.skill_names.join(', ')}`}
                meta={`${p.version ? `v${p.version} · ` : ''}스킬 ${p.skill_names.length}개`}
                active={p.is_active}
                onToggle={() => toggle(p)}
                onDelete={() => remove(p)}
              />
            ))}
          </div>
        )}
      </div>
      {dialog && (
        <GithubDialog
          title="GitHub 에서 플러그인 추가"
          hint="`.claude-plugin/plugin.json`(또는 marketplace.json)이 있는 저장소 URL 을 입력하세요. 플러그인에 포함된 스킬이 함께 설치됩니다. (명령어·서브에이전트·MCP 설정은 설치되지 않습니다)"
          placeholder="https://github.com/owner/repo"
          onInstall={install}
          onClose={() => setDialog(false)}
        />
      )}
    </CustomizeLayout>
  )
}

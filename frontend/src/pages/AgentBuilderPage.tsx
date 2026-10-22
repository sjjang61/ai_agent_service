import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Check, History, Loader2, Rocket } from 'lucide-react'
import CustomizeLayout from '../components/skills/CustomizeLayout'
import { Modal, errorText, inputCls, primaryBtn } from '../components/skills/common'
import BuilderForm from '../components/agents/BuilderForm'
import PreviewChat from '../components/agents/PreviewChat'
import VersionsDialog from '../components/agents/VersionsDialog'
import { agentsApi } from '../api/agents'
import type { AgentConfig, Catalog, CustomAgent, SaveResult, ValidationIssue } from '../types/customAgent'

type Save = 'saved' | 'dirty' | 'saving' | 'error'

export default function AgentBuilderPage() {
  const { agentId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: loaded, error: loadError } = useQuery<CustomAgent>({
    queryKey: ['agent', agentId],
    queryFn: async () => (await agentsApi.get(agentId)).data,
    staleTime: Infinity, // 편집 중에는 서버 값으로 덮어쓰지 않는다
    refetchOnWindowFocus: false,
    retry: false,
  })
  const { data: catalog } = useQuery<Catalog>({ queryKey: ['agent-catalog'], queryFn: async () => (await agentsApi.catalog()).data })

  const [agent, setAgent] = useState<CustomAgent | null>(null)
  const [meta, setMeta] = useState({ name: '', description: '', icon: '🤖' })
  const [config, setConfig] = useState<AgentConfig | null>(null)
  const [issues, setIssues] = useState<ValidationIssue[]>([])
  const [save, setSave] = useState<Save>('saved')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [publishing, setPublishing] = useState(false)
  const [note, setNote] = useState('')
  const [publishError, setPublishError] = useState<string | null>(null)
  const [showVersions, setShowVersions] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const latest = useRef<{ meta: typeof meta; config: AgentConfig | null }>({ meta, config })
  latest.current = { meta, config }
  const hydrated = useRef(false)

  const hydrate = useCallback((a: CustomAgent) => {
    setAgent(a)
    setMeta({ name: a.name, description: a.description, icon: a.icon })
    setConfig(a.config)
  }, [])

  useEffect(() => { hydrated.current = false }, [agentId])
  useEffect(() => {
    if (loaded && !hydrated.current) {
      hydrated.current = true
      hydrate(loaded)
      agentsApi.validate(loaded.config).then((r) => setIssues(r.data)).catch(() => undefined)
    }
  }, [loaded, hydrate])

  const flush = useCallback(async () => {
    clearTimeout(timer.current)
    const { meta: m, config: c } = latest.current
    if (!c || !m.name.trim()) return
    setSave('saving')
    try {
      const res = await agentsApi.update(agentId, { name: m.name, description: m.description, icon: m.icon, config: c })
      const r = res.data as SaveResult
      setAgent(r.agent)
      setIssues(r.issues)
      setSaveError(null)
      setSave('saved')
      queryClient.invalidateQueries({ queryKey: ['agents'] })
    } catch (e) {
      setSaveError(errorText(e, '저장하지 못했습니다'))
      setSave('error')
    }
  }, [agentId, queryClient])

  const schedule = () => {
    setSave('dirty')
    clearTimeout(timer.current)
    timer.current = setTimeout(flush, 900)
  }
  useEffect(() => () => { clearTimeout(timer.current) }, [])

  const hasErrors = issues.some((i) => i.level === 'error')

  const publish = async () => {
    setPublishError(null)
    try {
      await flush()
      const res = await agentsApi.publish(agentId, note)
      const r = res.data as SaveResult
      setAgent(r.agent)
      setIssues(r.issues)
      setPublishing(false)
      setNote('')
      queryClient.invalidateQueries({ queryKey: ['agents'] })
    } catch (e) {
      setPublishError(errorText(e, '발행하지 못했습니다'))
    }
  }

  if (loadError) {
    return (
      <CustomizeLayout active="agents">
        <div className="p-10 text-content-secondary">
          에이전트를 찾을 수 없습니다.{' '}
          <button onClick={() => navigate('/agents')} className="text-accent-primary underline border-none bg-transparent cursor-pointer">목록으로</button>
        </div>
      </CustomizeLayout>
    )
  }

  const statusText = { saved: '저장됨', dirty: '변경됨', saving: '저장 중…', error: saveError ?? '저장 실패' }[save]
  const version = agent?.published_version

  return (
    <CustomizeLayout active="agents">
      <header className="h-[56px] border-b border-border flex items-center gap-3 px-5 flex-shrink-0">
        <button onClick={async () => { await flush(); navigate('/agents') }} aria-label="목록으로" title="목록으로" className="text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer"><ArrowLeft size={18} /></button>
        <span className="text-xl" aria-hidden>{meta.icon}</span>
        <h1 className="text-[16px] font-semibold text-content-primary truncate">{meta.name || '이름 없음'}</h1>
        {version != null ? (
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-accent-green/15 text-accent-green flex-shrink-0">v{version}{agent?.has_unpublished_changes ? ' · 수정됨' : ''}</span>
        ) : (
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-surface-tertiary text-content-tertiary flex-shrink-0">미발행</span>
        )}
        <span className={`flex items-center gap-1.5 text-xs ${save === 'error' ? 'text-accent-red' : 'text-content-tertiary'}`}>
          {save === 'saving' ? <Loader2 size={12} className="animate-spin" /> : save === 'saved' ? <Check size={12} /> : null}
          {statusText}
        </span>
        <div className="flex-1" />
        <button onClick={() => setShowVersions(true)} disabled={!agent} className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[13px] border border-border text-content-secondary hover:bg-surface-hover bg-transparent cursor-pointer disabled:opacity-40">
          <History size={14} /> 버전
        </button>
        <button onClick={() => { setPublishError(null); setPublishing(true) }} disabled={!agent || hasErrors || save === 'saving'} title={hasErrors ? '오류를 먼저 해결하세요' : '현재 설정을 새 버전으로 발행'} className={primaryBtn}>
          <Rocket size={14} /> 발행
        </button>
      </header>

      {config && (
        <div className="flex-1 min-h-0 grid grid-cols-1 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
          <div className="min-h-0 border-r border-border">
            <BuilderForm
              name={meta.name}
              description={meta.description}
              icon={meta.icon}
              config={config}
              catalog={catalog}
              issues={issues}
              onMeta={(m) => { setMeta((x) => ({ ...x, ...m })); schedule() }}
              onConfig={(c) => { setConfig(c); schedule() }}
            />
          </div>
          <div className="min-h-0 hidden xl:block">
            <PreviewChat agentId={agentId} config={config} starters={config.prompt.starters} />
          </div>
        </div>
      )}

      {publishing && (
        <Modal title="새 버전 발행" onClose={() => setPublishing(false)}>
          <div className="space-y-3">
            <p className="text-[13px] text-content-secondary">
              현재 설정을 v{(version ?? 0) + 1}로 발행합니다. 새 대화와 이 에이전트를 지정한 예약은 발행된 버전으로 실행되고, 이미 시작한 대화는 기존 버전을 유지합니다.
            </p>
            <div className="space-y-1.5">
              <label htmlFor="publish-note" className="block text-[13px] font-medium text-content-primary">변경 메모 (선택)</label>
              <input id="publish-note" autoFocus value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} placeholder="예: 검색 도구 추가, 말투 수정" className={inputCls} />
            </div>
            {issues.filter((i) => i.level === 'warning').length > 0 && (
              <ul className="text-xs text-accent-amber list-disc pl-5 space-y-0.5">
                {issues.filter((i) => i.level === 'warning').map((i, k) => <li key={k}>{i.message}</li>)}
              </ul>
            )}
            {publishError && <p className="text-[13px] text-accent-red">{publishError}</p>}
            <div className="flex justify-end gap-2">
              <button onClick={() => setPublishing(false)} className="px-4 py-2.5 text-[13px] text-content-secondary border-none bg-transparent cursor-pointer">취소</button>
              <button onClick={publish} className={primaryBtn}>발행</button>
            </div>
          </div>
        </Modal>
      )}
      {showVersions && agent && (
        <VersionsDialog
          agent={agent}
          onClose={() => setShowVersions(false)}
          onChanged={(a) => {
            // 초안 불러오기(restore)면 폼도 갱신하고, 롤백이면 상태 배지만 바뀐다
            const draftChanged = JSON.stringify(a.config) !== JSON.stringify(latest.current.config)
            setAgent(a)
            if (draftChanged) { setConfig(a.config); agentsApi.validate(a.config).then((r) => setIssues(r.data)).catch(() => undefined) }
            queryClient.invalidateQueries({ queryKey: ['agents'] })
          }}
        />
      )}
    </CustomizeLayout>
  )
}

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, MessageSquarePlus, Pencil, Plus, Trash2 } from 'lucide-react'
import SettingsPage from '../components/skills/SettingsPage'
import { Modal, errorText, inputCls, primaryBtn } from '../components/skills/common'
import { AGENT_TEMPLATES, type AgentTemplate } from '../components/agents/templates'
import { agentsApi } from '../api/agents'
import { chatApi } from '../api/chat'
import { useChatStore } from '../store/chatStore'
import type { Conversation } from '../types/chat'
import type { CustomAgentSummary } from '../types/customAgent'

function StatusBadge({ a }: { a: CustomAgentSummary }) {
  if (a.published_version === null)
    return <span className="text-[11px] px-2 py-0.5 rounded-full bg-surface-tertiary text-content-tertiary">미발행</span>
  return (
    <span className="flex items-center gap-1.5">
      <span className="text-[11px] px-2 py-0.5 rounded-full bg-accent-green/15 text-accent-green">v{a.published_version} 발행됨</span>
      {a.has_unpublished_changes && (
        <span className="text-[11px] px-2 py-0.5 rounded-full bg-accent-amber/15 text-accent-amber">수정됨</span>
      )}
    </span>
  )
}

function NewAgentDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const [tpl, setTpl] = useState<AgentTemplate>(AGENT_TEMPLATES[0])
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const create = useMutation({
    mutationFn: async () =>
      (await agentsApi.create({ name: name.trim() || tpl.name, description: tpl.key === 'blank' ? '' : tpl.description, icon: tpl.icon, config: tpl.config })).data,
    onSuccess: (r) => onCreated(r.agent.id),
    onError: (e) => setError(errorText(e, '만들지 못했습니다')),
  })
  return (
    <Modal title="새 에이전트" onClose={onClose}>
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-2">
          {AGENT_TEMPLATES.map((t) => (
            <button
              key={t.key}
              onClick={() => setTpl(t)}
              className={`text-left p-3 rounded-[var(--radius-lg)] border cursor-pointer transition-colors ${
                tpl.key === t.key ? 'border-accent-primary bg-accent-primary/10' : 'border-border bg-surface-secondary hover:bg-surface-hover'
              }`}
            >
              <div className="text-xl">{t.icon}</div>
              <div className="text-[13px] font-medium text-content-primary mt-1">{t.key === 'blank' ? '빈 에이전트' : t.name}</div>
              <div className="text-xs text-content-tertiary mt-0.5">{t.description}</div>
            </button>
          ))}
        </div>
        <div className="space-y-1.5">
          <label className="block text-[13px] font-medium text-content-primary">이름</label>
          <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder={tpl.name} maxLength={100} className={inputCls} />
        </div>
        {error && <p className="text-[13px] text-accent-red">{error}</p>}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2.5 text-[13px] text-content-secondary border-none bg-transparent cursor-pointer">취소</button>
          <button onClick={() => create.mutate()} disabled={create.isPending} className={primaryBtn}>만들기</button>
        </div>
      </div>
    </Modal>
  )
}

export default function AgentsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { addConversation } = useChatStore()
  const { data: agents = [], isLoading } = useQuery<CustomAgentSummary[]>({
    queryKey: ['agents'],
    queryFn: async () => (await agentsApi.list()).data,
  })
  const [creating, setCreating] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['agents'] })

  const startChat = async (a: CustomAgentSummary) => {
    try {
      const res = await chatApi.createConversation({ title: 'New Conversation', agent_id: a.id })
      addConversation(res.data as Conversation)
      navigate(`/chat/${res.data.id}`)
    } catch (e) {
      setNotice(errorText(e, '대화를 시작하지 못했습니다'))
    }
  }
  const duplicate = async (a: CustomAgentSummary) => {
    try { await agentsApi.duplicate(a.id); refresh() } catch (e) { setNotice(errorText(e, '복제하지 못했습니다')) }
  }
  const remove = async (a: CustomAgentSummary) => {
    if (!confirm(`'${a.name}' 에이전트를 삭제할까요? 이 에이전트로 한 기존 대화는 유지됩니다.`)) return
    try { await agentsApi.remove(a.id); refresh() } catch (e) { setNotice(errorText(e, '삭제하지 못했습니다')) }
  }

  const iconBtn = 'w-8 h-8 flex items-center justify-center rounded-full text-content-tertiary hover:text-content-primary hover:bg-surface-hover border-none bg-transparent cursor-pointer'

  return (
    <SettingsPage active="agents" title="에이전트" subtitle="프롬프트·도구·스킬·MCP를 직접 정한 나만의 에이전트를 만들고, 발행해서 채팅과 예약에서 사용합니다.">
      <div className="flex justify-end mb-4">
        <button onClick={() => setCreating(true)} className={primaryBtn}>
          <Plus size={14} /> 새 에이전트
        </button>
      </div>
      {notice && <div className="mb-4 px-4 py-2.5 rounded-[var(--radius-md)] text-[13px] border text-accent-red border-accent-red/30">{notice}</div>}

      {isLoading ? (
        <div className="text-content-tertiary text-sm py-12 text-center">불러오는 중...</div>
      ) : agents.length === 0 ? (
        <div className="text-content-muted text-sm py-12 text-center border border-dashed border-border rounded-[var(--radius-lg)]">
          아직 만든 에이전트가 없습니다. 템플릿으로 빠르게 시작해 보세요.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {agents.map((a) => (
            <div key={a.id} className="group p-4 rounded-[var(--radius-lg)] border border-border bg-surface-secondary hover:border-accent-primary/60 transition-colors">
              <div className="flex items-start gap-3">
                <div className="w-11 h-11 rounded-[var(--radius-md)] bg-surface-tertiary flex items-center justify-center text-2xl flex-shrink-0">{a.icon}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[15px] font-semibold text-content-primary truncate">{a.name}</span>
                    <StatusBadge a={a} />
                  </div>
                  <p className="text-[13px] text-content-secondary mt-0.5 line-clamp-2">{a.description || '설명 없음'}</p>
                </div>
              </div>
              <div className="flex items-center gap-1 mt-3">
                <button
                  onClick={() => startChat(a)}
                  disabled={a.published_version === null}
                  title={a.published_version === null ? '발행 후 대화를 시작할 수 있습니다' : '이 에이전트로 새 대화 시작'}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[13px] border border-border bg-transparent text-content-primary cursor-pointer hover:bg-surface-hover disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <MessageSquarePlus size={14} /> 대화 시작
                </button>
                <div className="flex-1" />
                <button onClick={() => navigate(`/agents/${a.id}`)} title="편집" aria-label="편집" className={iconBtn}><Pencil size={15} /></button>
                <button onClick={() => duplicate(a)} title="복제" aria-label="복제" className={iconBtn}><Copy size={15} /></button>
                <button onClick={() => remove(a)} title="삭제" aria-label="삭제" className={`${iconBtn} hover:!text-accent-red`}><Trash2 size={15} /></button>
              </div>
            </div>
          ))}
        </div>
      )}
      {creating && <NewAgentDialog onClose={() => setCreating(false)} onCreated={(id) => navigate(`/agents/${id}`)} />}
    </SettingsPage>
  )
}

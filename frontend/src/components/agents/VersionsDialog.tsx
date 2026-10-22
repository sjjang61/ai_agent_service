import { useQuery } from '@tanstack/react-query'
import { Modal, errorText } from '../skills/common'
import { agentsApi } from '../../api/agents'
import type { AgentVersion, CustomAgent } from '../../types/customAgent'
import { useState } from 'react'

interface Props {
  agent: CustomAgent
  onClose: () => void
  /** 서버에서 바뀐 에이전트(초안/현재 버전)를 반영한다 */
  onChanged: (a: CustomAgent) => void
}

/** 발행된 버전 목록: 초안으로 불러오기, 이전 버전으로 롤백 */
export default function VersionsDialog({ agent, onClose, onChanged }: Props) {
  const { data: versions = [], refetch, isLoading } = useQuery<AgentVersion[]>({
    queryKey: ['agent-versions', agent.id],
    queryFn: async () => (await agentsApi.versions(agent.id)).data,
  })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const act = async (fn: () => Promise<{ data: CustomAgent }>) => {
    setBusy(true)
    setError(null)
    try {
      onChanged((await fn()).data)
      await refetch()
    } catch (e) {
      setError(errorText(e, '실행하지 못했습니다'))
    } finally {
      setBusy(false)
    }
  }
  const btn = 'px-3 py-1 rounded-full text-xs border border-border text-content-secondary hover:bg-surface-hover bg-transparent cursor-pointer disabled:opacity-40'

  return (
    <Modal title="버전 기록" onClose={onClose}>
      <div className="space-y-2">
        {isLoading && <p className="text-sm text-content-tertiary">불러오는 중...</p>}
        {!isLoading && versions.length === 0 && <p className="text-sm text-content-muted">아직 발행한 버전이 없습니다.</p>}
        {versions.map((v) => (
          <div key={v.id} className="flex items-center gap-3 p-3 rounded-[var(--radius-md)] border border-border bg-surface-secondary">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-[14px] font-semibold text-content-primary">v{v.version}</span>
                {v.is_current && <span className="text-[11px] px-2 py-0.5 rounded-full bg-accent-green/15 text-accent-green">현재</span>}
                <span className="text-xs text-content-tertiary">{new Date(v.created_at).toLocaleString()}</span>
              </div>
              {v.note && <p className="text-xs text-content-secondary mt-0.5 truncate">{v.note}</p>}
            </div>
            <button disabled={busy} className={btn} onClick={() => act(() => agentsApi.restoreVersion(agent.id, v.version))} title="이 버전의 설정을 편집 중인 초안으로 불러옵니다">초안으로 불러오기</button>
            {!v.is_current && (
              <button disabled={busy} className={btn} onClick={() => act(() => agentsApi.activateVersion(agent.id, v.version))} title="새 대화와 예약이 이 버전을 쓰도록 되돌립니다">이 버전으로 롤백</button>
            )}
          </div>
        ))}
        {error && <p className="text-[13px] text-accent-red">{error}</p>}
        <p className="text-xs text-content-tertiary pt-1">이미 시작한 대화는 시작할 때의 버전을 계속 사용합니다. 예약은 현재 버전으로 실행됩니다.</p>
      </div>
    </Modal>
  )
}

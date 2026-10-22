import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Layers, Loader2, MessageSquare, Square, Trash2 } from 'lucide-react'
import axios from 'axios'
import { sandboxApi, type SandboxInstance } from '../../api/sandbox'
import { T } from '../skills/typography'

function when(iso: string | null): string {
  if (!iso) return '-'
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z')
  return isNaN(d.getTime()) ? '-' : d.toLocaleString()
}

/** 내 sandbox 전체: 사용자 공용 1개(스페이스 대화·기존 파일)와 대화방별 sandbox. 중지(백업 후)·삭제할 수 있다. */
export default function SandboxInstances() {
  const qc = useQueryClient()
  const { data = [], isLoading } = useQuery<SandboxInstance[]>({
    queryKey: ['sandbox-instances'],
    queryFn: async () => (await sandboxApi.listInstances()).data,
    refetchInterval: 15000,
  })
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['sandbox-instances'] })
    qc.invalidateQueries({ queryKey: ['sandbox-status'] })
    qc.invalidateQueries({ queryKey: ['sandbox-artifacts'] })
  }
  const stop = useMutation({
    mutationFn: (id: string) => sandboxApi.stopInstance(id),
    onSuccess: refresh,
    onError: (e) => alert(axios.isAxiosError(e) && typeof e.response?.data?.detail === 'string' ? e.response.data.detail : '중지하지 못했습니다'),
  })
  const del = useMutation({ mutationFn: (id: string) => sandboxApi.deleteInstance(id), onSuccess: refresh })

  const onDelete = (s: SandboxInstance) => {
    const name = s.scope === 'shared' ? '공용 sandbox' : `'${s.conversation_title ?? s.conversation_id}' 대화의 sandbox`
    if (confirm(`${name}를 삭제할까요?\n작업 파일과 백업이 모두 사라지며 되돌릴 수 없습니다.`)) del.mutate(s.id)
  }

  return (
    <div className="bg-surface-secondary rounded-xl p-6 border border-border">
      <h3 className={`${T.section} mb-1`}>내 Sandbox 목록</h3>
      <p className={`${T.itemDesc} mb-4`}>대화방마다 독립된 sandbox 가 만들어지고, 스페이스에서 시작한 대화는 공용 sandbox 를 함께 씁니다. 5분 동안 쓰지 않으면 백업 후 자동 종료됩니다.</p>
      {isLoading ? (
        <p className="text-sm text-content-muted">불러오는 중...</p>
      ) : data.length === 0 ? (
        <p className="text-sm text-content-muted">아직 만들어진 sandbox 가 없습니다.</p>
      ) : (
        <ul className="divide-y divide-border">
          {data.map((s) => (
            <li key={s.id} className="flex items-center gap-3 py-2.5">
              {s.scope === 'shared' ? <Layers size={15} className="text-accent-primary flex-shrink-0" /> : <MessageSquare size={15} className="text-content-tertiary flex-shrink-0" />}
              <div className="min-w-0 flex-1">
                <div className={`${T.itemTitle} truncate`}>
                  {s.scope === 'shared' ? (
                    '공용 sandbox (스페이스 대화 · 이전 파일)'
                  ) : s.conversation_title ? (
                    <Link to={`/chat/${s.conversation_id}`} className="hover:underline">{s.conversation_title}</Link>
                  ) : (
                    '(삭제된 대화)'
                  )}
                </div>
                <div className="text-xs text-content-muted">마지막 사용 {when(s.last_used_at)}</div>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded-full ${s.status === 'running' ? 'bg-accent-green/15 text-accent-green' : 'bg-surface-tertiary text-content-muted'}`}>
                {s.status === 'running' ? '실행 중' : '중지됨'}
              </span>
              {s.status === 'running' && (
                <button onClick={() => stop.mutate(s.id)} disabled={stop.isPending} title="백업 후 중지" aria-label="중지" className="p-1.5 text-content-secondary hover:text-content-primary border-none bg-transparent cursor-pointer disabled:opacity-40">
                  {stop.isPending && stop.variables === s.id ? <Loader2 size={14} className="animate-spin" /> : <Square size={14} />}
                </button>
              )}
              <button onClick={() => onDelete(s)} title="삭제" aria-label="삭제" className="p-1.5 text-content-secondary hover:text-accent-red border-none bg-transparent cursor-pointer">
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Loader2, RotateCcw, Trash2 } from 'lucide-react'
import IconBar from '../components/layout/IconBar'
import Sidebar from '../components/chat/Sidebar'
import { driveApi, driveError } from '../api/drive'
import { NodeIcon, formatBytes } from '../components/drive/driveUtils'
import { formatFullDate } from '../utils/time'

/** Drive 휴지통: 삭제한 항목(묶음의 최상위)을 복원하거나 영구 삭제한다. 보관 기간이 지나면 자동으로 영구 삭제된다. */
export default function DriveTrashPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const [confirmEmpty, setConfirmEmpty] = useState(false)
  const { data, isLoading, isError, error: loadError, refetch } = useQuery({ queryKey: ['drive', 'trash'], queryFn: driveApi.trash, retry: false })
  const after = () => { setError(null); setConfirmEmpty(false); qc.invalidateQueries({ queryKey: ['drive'] }) }
  const fail = (fallback: string) => (e: unknown) => { setConfirmEmpty(false); setError(driveError(e, fallback)) }
  const restore = useMutation({ mutationFn: (id: string) => driveApi.restore([id]), onSuccess: after, onError: fail('복원하지 못했습니다') })
  const purge = useMutation({ mutationFn: (id: string) => driveApi.purge([id]), onSuccess: after, onError: fail('영구 삭제하지 못했습니다') })
  const empty = useMutation({ mutationFn: () => driveApi.emptyTrash(), onSuccess: after, onError: fail('휴지통을 비우지 못했습니다') })
  const nodes = data?.nodes ?? []
  const busy = restore.isPending || purge.isPending || empty.isPending
  const btn = 'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border border-border bg-transparent text-content-secondary hover:text-content-primary hover:bg-surface-hover cursor-pointer disabled:opacity-40'

  return (
    <div className="flex h-screen bg-surface-primary overflow-hidden">
      <IconBar />
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-auto">
        <div className="max-w-[860px] mx-auto px-6 pt-10 pb-24">
          <div className="flex items-center gap-2">
            <button onClick={() => navigate('/drive')} aria-label="Drive 로 돌아가기" className="p-1.5 rounded-lg border-none bg-transparent text-content-secondary hover:text-content-primary hover:bg-surface-hover cursor-pointer"><ArrowLeft size={18} /></button>
            <h1 className="flex-1 m-0 text-xl font-semibold text-content-primary">휴지통</h1>
            {nodes.length > 0 && (confirmEmpty
              ? <span className="flex items-center gap-2 text-xs text-content-secondary">모두 영구 삭제할까요?
                  <button onClick={() => empty.mutate()} disabled={busy} className={`${btn} !text-accent-red`}>삭제</button>
                  <button onClick={() => setConfirmEmpty(false)} className={btn}>취소</button></span>
              : <button onClick={() => setConfirmEmpty(true)} disabled={busy} className={btn}><Trash2 size={13} /> 휴지통 비우기</button>)}
          </div>
          <p className="mt-2 mb-4 text-xs text-content-tertiary">
            {data && data.retention_days > 0 ? `삭제한 항목은 ${data.retention_days}일 동안 보관된 뒤 영구 삭제됩니다.` : '삭제한 항목은 직접 영구 삭제할 때까지 보관됩니다.'} 휴지통의 파일도 용량에 포함됩니다.
          </p>
          {error && <p role="alert" className="m-0 mb-3 text-sm text-accent-red">{error}</p>}

          {isLoading ? (
            <div className="rounded-xl border border-border py-16 flex items-center justify-center text-sm text-content-muted"><Loader2 size={16} className="animate-spin mr-2" /> 불러오는 중...</div>
          ) : isError ? (
            <div role="alert" className="rounded-xl border border-border py-12 text-center text-sm">
              <p className="m-0 mb-3 text-accent-red">{driveError(loadError, '휴지통을 불러오지 못했습니다')}</p>
              <button onClick={() => refetch()} className={btn}>다시 시도</button>
            </div>
          ) : nodes.length === 0 ? (
            <div className="rounded-xl border border-border py-14 text-center text-sm text-content-muted">휴지통이 비어 있습니다</div>
          ) : (
            <ul className="m-0 p-0 list-none rounded-xl border border-border">
              {nodes.map((n) => (
                <li key={n.id} className="flex items-center gap-3 px-4 py-3 border-b last:border-b-0 border-border">
                  <NodeIcon node={n} />
                  <span className="flex-1 min-w-0 truncate text-sm text-content-primary">{n.name}</span>
                  <span className="w-20 text-right text-xs text-content-tertiary">{n.type === 'file' ? formatBytes(n.size_bytes ?? 0) : '폴더'}</span>
                  <span className="w-28 text-right text-xs text-content-tertiary" title="삭제한 날짜">{n.trashed_at ? formatFullDate(n.trashed_at) : ''}</span>
                  <button onClick={() => restore.mutate(n.id)} disabled={busy} className={btn}><RotateCcw size={13} /> 복원</button>
                  <button onClick={() => purge.mutate(n.id)} disabled={busy} className={`${btn} !text-accent-red`}>영구 삭제</button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  )
}

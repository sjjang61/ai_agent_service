import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, X } from 'lucide-react'
import { ACTIVE, formatDuration, functionsApi, type RunDetail } from '../../api/functions'
import { driveError } from '../../api/drive'
import { formatFullDateTime } from '../../utils/time'
import JsonBlock from './JsonBlock'
import StatusBadge from './StatusBadge'

/** 실행 1건의 상세: 상태·시각·소요 시간, 입력·결과·오류, 로그. 실행 중이면 자동으로 갱신하고 취소할 수 있다. */
export default function RunDetailDialog({ runId, functionName, onClose }: { runId: string; functionName?: string; onClose: () => void }) {
  const qc = useQueryClient()
  const [cancelErr, setCancelErr] = useState<string | null>(null)
  const { data: run, isLoading, isError, error } = useQuery<RunDetail>({
    queryKey: ['fn-run', runId],
    queryFn: () => functionsApi.run(runId),
    refetchInterval: (q) => (q.state.data && ACTIVE.includes(q.state.data.status) ? 1500 : false),
    retry: false,
  })
  const finished = !!run && !ACTIVE.includes(run.status)
  const { data: logs } = useQuery({ queryKey: ['fn-run-logs', runId, run?.status], queryFn: () => functionsApi.logs(runId), enabled: finished, retry: false })

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const cancel = async () => {
    setCancelErr(null)
    try {
      await functionsApi.cancel(runId)
      qc.invalidateQueries({ queryKey: ['fn-run', runId] })
      qc.invalidateQueries({ queryKey: ['fn-runs'] })
    } catch (e) { setCancelErr(driveError(e, '취소하지 못했습니다')) }
  }

  const row = (k: string, v: React.ReactNode) => <div className="flex gap-2"><dt className="w-20 flex-shrink-0 text-content-tertiary">{k}</dt><dd className="m-0 text-content-primary">{v}</dd></div>

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-[6vh] px-4" onMouseDown={onClose}>
      <div role="dialog" aria-label="실행 상세" onMouseDown={(e) => e.stopPropagation()} className="w-full max-w-2xl max-h-[88vh] flex flex-col rounded-xl border border-border bg-surface-primary shadow-xl">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
          <h2 className="m-0 text-sm font-semibold text-content-primary truncate">{functionName ?? '실행'} <span className="font-normal text-content-tertiary">· {runId.slice(0, 8)}</span></h2>
          {run && <StatusBadge status={run.status} />}
          <div className="flex-1" />
          {run && ACTIVE.includes(run.status) && (
            <button onClick={cancel} disabled={run.cancel_requested} className="px-2.5 py-1 rounded-lg text-xs border border-accent-red/50 bg-transparent text-accent-red hover:bg-accent-red/10 cursor-pointer disabled:opacity-50">
              {run.cancel_requested ? '취소 중...' : '취소'}
            </button>
          )}
          <button onClick={onClose} aria-label="닫기" className="p-1 border-none bg-transparent text-content-muted hover:text-content-primary cursor-pointer"><X size={15} /></button>
        </div>
        <div className="p-4 space-y-4 overflow-auto text-xs">
          {isLoading && <div className="flex items-center gap-2 text-content-muted"><Loader2 size={14} className="animate-spin" /> 불러오는 중...</div>}
          {isError && <p role="alert" className="m-0 text-accent-red">{driveError(error, '실행 기록을 불러오지 못했습니다')}</p>}
          {cancelErr && <p role="alert" className="m-0 text-accent-red">{cancelErr}</p>}
          {run && (
            <>
              <dl className="m-0 space-y-1">
                {row('버전', `v${run.version}`)}
                {row('트리거', run.trigger)}
                {row('요청', formatFullDateTime(run.queued_at))}
                {row('시작', formatFullDateTime(run.started_at))}
                {row('종료', formatFullDateTime(run.finished_at))}
                {row('소요 시간', formatDuration(run.duration_ms))}
                {row('콜드 스타트', formatDuration(run.cold_start_ms))}
                {run.exit_code != null && row('종료 코드', run.exit_code)}
              </dl>
              {run.error && (
                <div role="alert" className="p-3 rounded-lg border border-accent-red/40 bg-accent-red/10 text-accent-red">
                  <div className="font-semibold">{run.error.type}</div>
                  <div className="mt-0.5 whitespace-pre-wrap break-words">{run.error.message}</div>
                </div>
              )}
              <JsonBlock label="입력" value={run.input} />
              {run.status === 'succeeded' && <JsonBlock label="결과" value={run.result} empty="null" />}
              {finished && (
                <div>
                  <JsonBlock label={`로그${logs?.truncated || run.log_truncated ? ' (길어서 일부만 저장됨)' : ''}`} value={logs?.log ?? ''} empty="출력된 로그가 없습니다" />
                </div>
              )}
              {!finished && <p className="m-0 text-content-tertiary">로그는 실행이 끝나면 표시됩니다.</p>}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

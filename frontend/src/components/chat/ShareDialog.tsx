import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Copy, Link2, Loader2, RefreshCw, X } from 'lucide-react'
import { shareApi, shareUrl, type ShareStatus } from '../../api/share'
import { formatKoreanDateTime } from '../../utils/time'

const errText = (e: unknown, fallback: string) => (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback

/** 대화 공유: 로그인 없이 읽는 링크를 만들고, 최신 내용으로 갱신하거나 해제한다.
 *  공유 링크에는 공유한 시점의 사용자·AI 글과 표·차트만 담긴다 (도구 실행 기록·첨부파일은 담기지 않는다). */
export default function ShareDialog({ conversationId, onClose }: { conversationId: string; onClose: () => void }) {
  const qc = useQueryClient()
  const key = ['share', conversationId]
  const { data, isLoading } = useQuery<ShareStatus>({ queryKey: key, queryFn: async () => (await shareApi.status(conversationId)).data, retry: false })
  const [busy, setBusy] = useState<'share' | 'unshare' | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const run = async (kind: 'share' | 'unshare') => {
    setBusy(kind)
    setErr(null)
    try {
      if (kind === 'share') qc.setQueryData(key, (await shareApi.share(conversationId)).data)
      else {
        await shareApi.unshare(conversationId)
        qc.setQueryData(key, { shared: false })
      }
    } catch (e) {
      setErr(errText(e, kind === 'share' ? '공유하지 못했습니다' : '공유를 해제하지 못했습니다'))
    } finally {
      setBusy(null)
    }
  }

  const link = data?.shared && data.path ? shareUrl(data.path) : ''
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      setErr('복사하지 못했습니다. 주소를 직접 선택해 복사하세요')
    }
  }
  const local = /^https?:\/\/(localhost|127\.|\[::1\])/.test(link)

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-[14vh] px-4" onMouseDown={onClose}>
      <div role="dialog" aria-label="대화 공유" onMouseDown={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-[var(--radius-lg)] border border-border bg-surface-primary shadow-xl">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
          <Link2 size={15} className="text-content-secondary" />
          <h2 className="flex-1 m-0 text-sm font-semibold text-content-primary">대화 공유</h2>
          <button onClick={onClose} aria-label="닫기" className="p-1 border-none bg-transparent text-content-muted hover:text-content-primary cursor-pointer"><X size={15} /></button>
        </div>

        <div className="p-4 space-y-3 text-xs text-content-secondary">
          {isLoading ? (
            <div className="flex items-center gap-2 py-4"><Loader2 size={14} className="animate-spin" /> 불러오는 중...</div>
          ) : !data?.shared ? (
            <>
              <p className="m-0 leading-relaxed">링크를 만들면 <b className="text-content-primary">링크를 아는 누구나 로그인 없이</b> 이 대화를 읽을 수 있습니다.</p>
              <ul className="m-0 pl-4 space-y-1 leading-relaxed">
                <li>지금까지의 대화를 복사해 보여 줍니다. 이후 대화는 <b>다시 업데이트</b>해야 반영됩니다.</li>
                <li>내 글과 AI 답변, 표·차트만 보입니다. 도구 실행 기록과 첨부파일은 공유되지 않습니다.</li>
                <li>언제든 공유를 해제하면 링크가 바로 끊깁니다.</li>
              </ul>
              <button onClick={() => run('share')} disabled={busy !== null}
                className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-[var(--radius-md)] text-xs font-medium bg-accent-primary text-white border-none cursor-pointer disabled:opacity-50">
                {busy === 'share' ? <Loader2 size={13} className="animate-spin" /> : <Link2 size={13} />} 공유 링크 만들기
              </button>
            </>
          ) : (
            <>
              <div className="flex items-center gap-1.5">
                <input readOnly value={link} onFocus={(e) => e.currentTarget.select()} aria-label="공유 링크"
                  className="flex-1 min-w-0 px-2.5 py-2 rounded-[var(--radius-md)] border border-border bg-surface-secondary text-content-primary text-xs" />
                <button onClick={copy} className="flex items-center gap-1 px-2.5 py-2 rounded-[var(--radius-md)] text-xs border border-border bg-surface-secondary text-content-primary hover:bg-surface-hover cursor-pointer">
                  {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? '복사됨' : '복사'}
                </button>
              </div>
              {local && <p className="m-0 text-accent-yellow leading-relaxed">이 주소는 내 컴퓨터(localhost)용이라 다른 사람은 열 수 없습니다. 서비스를 외부 주소로 열었을 때 만든 링크를 공유하세요.</p>}
              <p className="m-0 leading-relaxed">
                메시지 {data.message_count}개 · 조회 {data.view_count}회
                {data.shared_at && <> · {formatKoreanDateTime(data.shared_at)} 기준</>}
                {data.expires_at && <> · {formatKoreanDateTime(data.expires_at)}까지</>}
              </p>
              <div className="flex gap-2">
                <button onClick={() => run('share')} disabled={busy !== null} title="같은 주소에서 내용을 지금 대화로 바꿉니다"
                  className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-[var(--radius-md)] text-xs border border-border bg-surface-secondary text-content-primary hover:bg-surface-hover cursor-pointer disabled:opacity-50">
                  {busy === 'share' ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />} 최신 내용으로 업데이트
                </button>
                <button onClick={() => run('unshare')} disabled={busy !== null}
                  className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-[var(--radius-md)] text-xs border border-accent-red/50 bg-transparent text-accent-red hover:bg-accent-red/10 cursor-pointer disabled:opacity-50">
                  {busy === 'unshare' && <Loader2 size={13} className="animate-spin" />} 공유 해제
                </button>
              </div>
            </>
          )}
          {err && <p role="alert" className="m-0 text-accent-red">{err}</p>}
        </div>
      </div>
    </div>
  )
}

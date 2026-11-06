import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { LogIn } from 'lucide-react'
import { browserApi } from '../../api/browser'
import LiveBrowser from '../browser/LiveBrowser'

/** 브라우저 에이전트가 로그인을 요청하면 나타나는 카드. 실행 중인 마지막 답변에서만 폴링한다. */
export default function LoginRequestCard({ conversationId, active }: { conversationId: string; active: boolean }) {
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const { data, refetch } = useQuery({
    queryKey: ['login-request', conversationId],
    queryFn: async () => (await browserApi.loginRequest(conversationId)).data,
    enabled: active,
    refetchInterval: active ? 2000 : false,
  })
  if (!active || !data) return null

  const finish = async (cancelled: boolean) => {
    try {
      await browserApi.finishLogin(conversationId, cancelled)
      setOpen(false)
      setError('')
      refetch()
    } catch (e) {
      setError(axios.isAxiosError(e) && typeof e.response?.data?.detail === 'string' ? e.response.data.detail : '전달하지 못했습니다')
    }
  }

  return (
    <>
      <div className="mb-3 rounded-[var(--radius-lg)] border border-accent-blue/30 bg-surface-secondary p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-1">
          <LogIn size={16} className="text-accent-blue" />
          <h4 className="text-sm font-semibold text-content-primary">{data.site} 로그인이 필요합니다</h4>
        </div>
        <p className="text-xs text-content-secondary mb-3">
          {data.reason || '에이전트가 작업을 이어가려면 로그인이 필요합니다.'} 열린 브라우저에서 직접 로그인한 뒤 '로그인 완료'를 눌러 주세요.
          비밀번호와 인증 코드는 에이전트에 전달되지 않습니다.
        </p>
        <div className="flex items-center gap-2">
          <button onClick={() => setOpen(true)} className="px-4 py-2 bg-accent-primary hover:bg-accent-primary/90 text-white rounded-md text-sm font-medium border-none cursor-pointer">
            브라우저 열기
          </button>
          <button onClick={() => finish(true)} className="px-4 py-2 bg-surface-tertiary hover:bg-surface-hover text-content-secondary rounded-md text-sm font-medium border-none cursor-pointer">
            취소
          </button>
          {error && <span className="text-xs text-accent-red">{error}</span>}
        </div>
      </div>
      {open && (
        <LiveBrowser
          conversationId={conversationId}
          initialUrl={data.url || undefined}
          doneLabel="로그인 완료"
          onDone={() => finish(false)}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  )
}

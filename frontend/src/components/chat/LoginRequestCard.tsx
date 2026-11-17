import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { LogIn, ShieldAlert } from 'lucide-react'
import { browserApi } from '../../api/browser'
import type { DesktopChromeCheck, DesktopChromeImport } from '../../config/server'
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
  // 데스크톱 앱: 이 사이트의 로그인 쿠키가 로컬 Chrome 에 있는지 확인한다 (키체인 접근 없이 개수만 센다)
  const chrome = typeof window !== 'undefined' ? window.desktop?.chrome : undefined
  const isLocalLogin = !!data && data.local && data.kind !== 'approval'
  const [chromeInfo, setChromeInfo] = useState<DesktopChromeCheck | null>(null)
  const [chromeResult, setChromeResult] = useState<DesktopChromeImport | null>(null)
  const [importing, setImporting] = useState(false)
  const site = data?.site
  useEffect(() => {
    setChromeInfo(null)
    setChromeResult(null)
    if (!active || !isLocalLogin || !chrome) return
    let alive = true
    chrome.check().then((r) => alive && setChromeInfo(r)).catch(() => alive && setChromeInfo({ error: 'chrome-not-found' }))
    return () => { alive = false }
  }, [active, isLocalLogin, site, chrome])

  const importFromChrome = async () => {
    if (!chrome) return
    setImporting(true)
    try {
      setChromeResult(await chrome.importCookies())
    } catch {
      setChromeResult({ error: 'unsupported' })
    } finally {
      setImporting(false)
    }
  }

  if (!active || !data) return null

  const finish = async (cancelled: boolean, remember = false) => {
    try {
      await browserApi.finishLogin(conversationId, cancelled, remember)
      setOpen(false)
      setError('')
      refetch()
    } catch (e) {
      setError(axios.isAxiosError(e) && typeof e.response?.data?.detail === 'string' ? e.response.data.detail : '전달하지 못했습니다')
    }
  }

  if (data.kind === 'approval') {
    const always = data.level === 'ask_always'
    return (
      <div className="mb-3 rounded-[var(--radius-lg)] border border-accent-orange/40 bg-surface-secondary p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-1">
          <ShieldAlert size={16} className="text-accent-orange" />
          <h4 className="text-sm font-semibold text-content-primary">{data.site}에서 실행을 승인해 주세요{data.session && data.session !== data.site ? <span className="font-normal text-content-tertiary"> · {data.session}</span> : null}</h4>
        </div>
        <p className="text-xs text-content-secondary mb-1">
          에이전트가 <b className="text-content-primary">{data.action || '동작'}</b>
          {data.detail ? <> — “{data.detail}”</> : null}을(를) 하려고 합니다.
        </p>
        {data.reason && <p className="text-xs text-content-tertiary mb-3">{data.reason}</p>}
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={() => finish(false)} className="px-4 py-2 bg-accent-primary hover:bg-accent-primary/90 text-white rounded-md text-sm font-medium border-none cursor-pointer">
            승인
          </button>
          {!always && (
            <button onClick={() => finish(false, true)} className="px-4 py-2 bg-surface-tertiary hover:bg-surface-hover text-content-primary rounded-md text-sm font-medium border-none cursor-pointer">
              이 대화에서 {data.site}는 계속 허용
            </button>
          )}
          <button onClick={() => finish(true)} className="px-4 py-2 bg-surface-tertiary hover:bg-surface-hover text-content-secondary rounded-md text-sm font-medium border-none cursor-pointer">
            거부
          </button>
          {error && <span className="text-xs text-accent-red">{error}</span>}
        </div>
        {always && <p className="text-[11px] text-content-tertiary mt-2">되돌리기 어려운 동작이거나 금융·결제 사이트여서 매번 확인합니다.</p>}
      </div>
    )
  }

  return (
    <>
      <div className="mb-3 rounded-[var(--radius-lg)] border border-accent-blue/30 bg-surface-secondary p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-1">
          <LogIn size={16} className="text-accent-blue" />
          <h4 className="text-sm font-semibold text-content-primary">{data.site} 로그인이 필요합니다{data.session && data.session !== data.site ? <span className="font-normal text-content-tertiary"> · {data.session}</span> : null}</h4>
        </div>
        <p className="text-xs text-content-secondary mb-3">
          {data.reason || '에이전트가 작업을 이어가려면 로그인이 필요합니다.'}{' '}
          {data.local
            ? "오른쪽 앱 브라우저에서 직접 진행한 뒤 '완료'를 눌러 주세요."
            : "열린 브라우저에서 직접 로그인한 뒤 '로그인 완료'를 눌러 주세요."}
          비밀번호와 인증 코드는 에이전트에 전달되지 않습니다.
        </p>
        {data.local && chrome && chromeInfo && (chromeInfo.count ?? 0) > 0 && !chromeResult?.imported && (
          <div className="mb-3 rounded-md border border-border bg-surface-tertiary px-3 py-2 text-xs text-content-secondary flex items-center justify-between gap-3">
            <span>
              로컬 Chrome 에 <b className="text-content-primary">{chromeInfo.site}</b> 로그인 쿠키가 {chromeInfo.count}개 있습니다. 가져오면 직접 로그인하지 않아도 됩니다.
            </span>
            <button
              onClick={importFromChrome}
              disabled={importing}
              className="flex-shrink-0 px-3 py-1.5 bg-surface-secondary hover:bg-surface-hover text-content-primary border border-border rounded-md text-xs font-medium cursor-pointer disabled:opacity-50"
            >
              {importing ? '가져오는 중...' : 'Chrome 에서 가져오기'}
            </button>
          </div>
        )}
        {data.local && chrome && chromeInfo && chromeInfo.count === 0 && !chromeInfo.error && (
          <p className="mb-3 text-[11px] text-content-tertiary">로컬 Chrome 에 {chromeInfo.site} 로그인 쿠키가 없습니다. 오른쪽 브라우저에서 직접 로그인해 주세요.</p>
        )}
        {chromeResult && (
          <p className={`mb-3 text-xs ${chromeResult.imported ? 'text-accent-green' : 'text-content-tertiary'}`}>
            {chromeResult.imported
              ? `쿠키 ${chromeResult.imported}개를 가져와 오른쪽 브라우저를 새로고침했습니다. 로그인된 상태인지 확인한 뒤 '완료'를 눌러 주세요. 아직 로그인 화면이면 직접 로그인해 주세요.`
              : chromeResult.error === 'cancelled'
                ? '가져오기를 취소했습니다.'
                : chromeResult.error === 'keychain-denied'
                  ? 'macOS 키체인 접근이 허용되지 않아 가져오지 못했습니다. 직접 로그인해 주세요.'
                  : '쿠키를 가져오지 못했습니다. 직접 로그인해 주세요.'}
          </p>
        )}
        <div className="flex items-center gap-2">
          {data.local ? (
            <button onClick={() => finish(false)} className="px-4 py-2 bg-accent-primary hover:bg-accent-primary/90 text-white rounded-md text-sm font-medium border-none cursor-pointer">
              {data.reason.includes('CAPTCHA') ? '해결 완료' : '로그인 완료'}
            </button>
          ) : (
            <button onClick={() => setOpen(true)} className="px-4 py-2 bg-accent-primary hover:bg-accent-primary/90 text-white rounded-md text-sm font-medium border-none cursor-pointer">
              브라우저 열기
            </button>
          )}
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

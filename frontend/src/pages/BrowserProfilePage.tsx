import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Globe, Trash2 } from 'lucide-react'
import { browserApi, type BrowserProfile } from '../api/browser'
import type { DesktopChromeCheck, DesktopChromeImport } from '../config/server'
import SettingsPage from '../components/skills/SettingsPage'
import LiveBrowser from '../components/browser/LiveBrowser'
import { T } from '../components/skills/typography'
import { errorText, primaryBtn } from '../components/skills/common'
import { isDesktopShell } from '../store/desktopLayoutStore'
import { formatFullDateTime } from '../utils/time'

export default function BrowserProfilePage() {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const desktop = isDesktopShell()
  // 데스크톱 앱에서는 서버의 sandbox 브라우저 대신 앱의 로컬 브라우저를 연다 (에이전트도 같은 브라우저를 쓰고, 로그인은 앱에 유지된다)
  // Chrome 에서 로그인 가져오기: 구글처럼 내장 브라우저 로그인을 막는 사이트용. 앱 브라우저로 그 사이트를 연 뒤 로컬 Chrome 의 로그인 쿠키를 복사한다
  const chrome = typeof window !== 'undefined' ? window.desktop?.chrome : undefined
  const [impUrl, setImpUrl] = useState('https://mail.google.com')
  const [impInfo, setImpInfo] = useState<DesktopChromeCheck | null>(null)
  const [impResult, setImpResult] = useState<DesktopChromeImport | null>(null)
  const [impBusy, setImpBusy] = useState(false)
  const checkChrome = async () => {
    const b = window.desktop?.browser
    if (!chrome || !b?.navigate) return
    setImpBusy(true); setImpResult(null); setImpInfo(null)
    try {
      await b.setSplit?.(0.5)
      const u = /^https?:\/\//i.test(impUrl.trim()) ? impUrl.trim() : `https://${impUrl.trim()}`
      await b.navigate(u).catch(() => {})
      await new Promise((r) => setTimeout(r, 2500)) // 이동한 뒤의 주소(로그인 전 안내 페이지 등)로 확인한다
      setImpInfo(await chrome.check())
    } catch {
      setImpInfo({ error: 'chrome-not-found' })
    } finally {
      setImpBusy(false)
    }
  }
  const importChrome = async () => {
    if (!chrome) return
    setImpBusy(true)
    try {
      setImpResult(await chrome.importCookies())
    } catch {
      setImpResult({ error: 'unsupported' })
    } finally {
      setImpBusy(false)
    }
  }
  const openLogin = () => {
    const b = window.desktop?.browser
    if (desktop && b?.setSplit) {
      b.setSplit(0.5).catch(() => setError('앱 브라우저를 열지 못했습니다'))
      return
    }
    setOpen(true)
  }
  const { data } = useQuery<BrowserProfile>({
    queryKey: ['browser-profile'],
    queryFn: async () => (await browserApi.profile()).data,
  })
  const refresh = () => qc.invalidateQueries({ queryKey: ['browser-profile'] })
  const delDomain = useMutation({ mutationFn: (d: string) => browserApi.deleteDomain(d), onSuccess: refresh, onError: (e) => setError(errorText(e, '삭제하지 못했습니다')) })
  const delAll = useMutation({ mutationFn: () => browserApi.deleteProfile(), onSuccess: refresh, onError: (e) => setError(errorText(e, '삭제하지 못했습니다')) })

  return (
    <SettingsPage active="browser" title="브라우저 로그인" subtitle="에이전트가 웹사이트를 사용할 때 쓰는 로그인 상태를 관리합니다.">
      <div className="space-y-6 max-w-[720px]">
        {error && <div className="text-[13px] text-red-500">{error}</div>}

        <section className="space-y-2">
          <h2 className={T.section}>사이트에 로그인</h2>
          <p className={T.itemDesc}>
            서버의 브라우저를 화면에 열어 직접 로그인합니다. 로그인한 상태는 암호화되어 저장되고, 이후 모든 대화에서 다시 로그인하지 않고 쓸 수 있습니다.
            에이전트가 작업 중 로그인이 필요하면 채팅에서도 같은 브라우저가 열립니다.
          </p>
          <button onClick={openLogin} className={primaryBtn}>브라우저 열어 로그인</button>
          {desktop && <p className={T.itemDesc}>앱 오른쪽에 브라우저가 열립니다. 주소창에 사이트 주소를 입력해 직접 로그인하세요. 로그인 상태는 앱에 그대로 유지되어 에이전트도 같이 씁니다.</p>}
        </section>

        {desktop && chrome && (
          <section className="space-y-2">
            <h2 className={T.section}>Chrome 에서 로그인 가져오기</h2>
            <p className={T.itemDesc}>
              구글처럼 앱 브라우저에서 직접 로그인할 수 없는 사이트용입니다. 먼저 평소 쓰는 Chrome 에서 그 사이트에 로그인해 두세요.
              그다음 아래에서 사이트를 열어 로그인 쿠키를 확인하고 앱 브라우저로 복사합니다. 쿠키 값은 앱 안에서만 쓰이고 서버나 AI 에는 전달되지 않습니다.
            </p>
            <div className="flex gap-2">
              <input
                value={impUrl}
                onChange={(e) => setImpUrl(e.target.value)}
                placeholder="https://mail.google.com"
                className="flex-1 px-3 py-2 bg-surface-secondary border border-border rounded-md text-sm text-content-primary focus:outline-none focus:border-accent-primary"
              />
              <button onClick={checkChrome} disabled={impBusy || !impUrl.trim()} className={primaryBtn}>{impBusy ? '확인 중...' : '열고 Chrome 확인'}</button>
            </div>
            {impInfo && (
              impInfo.error ? (
                <p className={T.itemDesc}>{impInfo.error === 'chrome-not-found' ? '로컬 Chrome 을 찾지 못했습니다.' : impInfo.error === 'unsupported' ? '이 기능은 macOS 에서만 쓸 수 있습니다.' : '이 주소의 사이트를 확인하지 못했습니다.'}</p>
              ) : (impInfo.count ?? 0) > 0 ? (
                <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface-tertiary px-3 py-2 text-xs text-content-secondary">
                  <span>로컬 Chrome 에 <b className="text-content-primary">{impInfo.site}</b> 로그인 쿠키가 {impInfo.count}개 있습니다.</span>
                  <button onClick={importChrome} disabled={impBusy} className={primaryBtn}>Chrome 에서 가져오기</button>
                </div>
              ) : (
                <p className={T.itemDesc}>로컬 Chrome 에 {impInfo.site} 로그인 쿠키가 없습니다. Chrome 에서 먼저 로그인한 뒤 다시 확인하세요.</p>
              )
            )}
            {impResult && (
              <p className={T.itemDesc}>
                {impResult.imported
                  ? `쿠키 ${impResult.imported}개를 가져와 앱 브라우저를 새로고침했습니다. 로그인된 화면인지 확인해 주세요.`
                  : impResult.error === 'cancelled' ? '가져오기를 취소했습니다.'
                  : impResult.error === 'keychain-denied' ? 'macOS 키체인 접근이 허용되지 않아 가져오지 못했습니다.'
                  : '쿠키를 가져오지 못했습니다.'}
              </p>
            )}
          </section>
        )}

        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className={T.section}>로그인된 사이트</h2>
            {data?.has_profile && (
              <button
                onClick={() => { if (confirm('저장된 모든 사이트의 로그인 상태를 삭제할까요?')) delAll.mutate() }}
                className="text-[13px] text-content-muted hover:text-accent-red border-none bg-transparent cursor-pointer"
              >
                전체 삭제
              </button>
            )}
          </div>
          {!data?.has_profile ? (
            <p className={T.itemDesc}>저장된 로그인 상태가 없습니다.</p>
          ) : (
            <>
              <ul className="divide-y divide-border bg-surface-secondary border border-border rounded-xl">
                {data.domains.map((d) => (
                  <li key={d.domain} className="flex items-center gap-3 px-4 py-2.5">
                    <Globe size={15} className="text-content-tertiary flex-shrink-0" />
                    <span className={`${T.itemTitle} flex-1`}>{d.domain}</span>
                    <span className="text-xs text-content-muted">쿠키 {d.cookies}개</span>
                    <button
                      onClick={() => { if (confirm(`${d.domain} 의 로그인 상태를 삭제할까요?`)) delDomain.mutate(d.domain) }}
                      title="삭제" aria-label="삭제"
                      className="p-1.5 text-content-secondary hover:text-accent-red border-none bg-transparent cursor-pointer"
                    >
                      <Trash2 size={14} />
                    </button>
                  </li>
                ))}
              </ul>
              <p className="text-xs text-content-muted">마지막 저장 {formatFullDateTime(data.updated_at)} · {(data.size_bytes / 1024).toFixed(0)}KB / 2048KB</p>
            </>
          )}
        </section>

        <section className="space-y-1">
          <h2 className={T.section}>안내</h2>
          <ul className={`${T.itemDesc} list-disc pl-5 space-y-0.5`}>
            <li>서버 IP 에서 접속하므로 일부 사이트는 추가 인증을 요구하거나 계정을 제한할 수 있습니다.</li>
            <li>금융·결제 사이트의 로그인 상태는 저장하지 않습니다.</li>
            <li>사이트의 이용약관이 자동화를 제한하는지 확인하고, 읽기 위주로 사용하세요.</li>
          </ul>
        </section>
      </div>

      {open && (
        <LiveBrowser
          doneLabel="저장하고 닫기"
          onDone={() => { setOpen(false); refresh() }}
          onClose={() => { setOpen(false); refresh() }}
        />
      )}
    </SettingsPage>
  )
}

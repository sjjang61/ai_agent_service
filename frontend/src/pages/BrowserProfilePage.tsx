import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Globe, Trash2 } from 'lucide-react'
import { browserApi, type BrowserProfile } from '../api/browser'
import SettingsPage from '../components/skills/SettingsPage'
import LiveBrowser from '../components/browser/LiveBrowser'
import { T } from '../components/skills/typography'
import { errorText, primaryBtn } from '../components/skills/common'
import { formatFullDateTime } from '../utils/time'

export default function BrowserProfilePage() {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
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
          <button onClick={() => setOpen(true)} className={primaryBtn}>브라우저 열어 로그인</button>
        </section>

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
            <li>서버 IP 에서 접속하므로 일부 사이트(LinkedIn 등)는 추가 인증을 요구하거나 계정을 제한할 수 있습니다.</li>
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

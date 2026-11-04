import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ExternalLink, Send } from 'lucide-react'
import { channelsApi, type ChannelStatus } from '../api/channels'
import SettingsPage from '../components/skills/SettingsPage'
import { T } from '../components/skills/typography'
import { errorText, inputCls, primaryBtn } from '../components/skills/common'

const STATUS_LABEL: Record<string, { text: string; cls: string }> = {
  connected: { text: '연결됨', cls: 'bg-green-500/15 text-green-600' },
  pending: { text: '연결 대기', cls: 'bg-yellow-500/15 text-yellow-600' },
  error: { text: '오류', cls: 'bg-red-500/15 text-red-500' },
}

export default function ChannelsPage() {
  const qc = useQueryClient()
  const [token, setToken] = useState('')
  const [issued, setIssued] = useState<ChannelStatus | null>(null) // 코드는 발급 응답에만 있으므로 화면에서만 들고 있는다
  const [error, setError] = useState('')

  const { data } = useQuery<ChannelStatus>({
    queryKey: ['channel-telegram'],
    queryFn: async () => (await channelsApi.telegram()).data,
    refetchInterval: (q) => (q.state.data?.status === 'pending' ? 3000 : false), // 연결 완료를 자동 반영
  })
  const refresh = () => qc.invalidateQueries({ queryKey: ['channel-telegram'] })
  const fail = (e: unknown) => setError(errorText(e, '요청에 실패했습니다'))

  const connect = useMutation({
    mutationFn: () => channelsApi.connect(token.trim()),
    onSuccess: (r) => { setIssued(r.data); setToken(''); setError(''); refresh() },
    onError: fail,
  })
  const newCode = useMutation({
    mutationFn: () => channelsApi.newPairCode(),
    onSuccess: (r) => { setIssued(r.data); setError(''); refresh() },
    onError: fail,
  })
  const toggle = useMutation({ mutationFn: (v: boolean) => channelsApi.setEnabled(v), onSuccess: refresh, onError: fail })
  const notify = useMutation({ mutationFn: (v: boolean) => channelsApi.setNotify(v), onSuccess: refresh, onError: fail })
  const remove = useMutation({
    mutationFn: () => channelsApi.disconnect(),
    onSuccess: () => { setIssued(null); refresh() },
    onError: fail,
  })

  const st = data && data.configured ? STATUS_LABEL[data.status] : null
  const showCode = issued?.pair_code && data?.status === 'pending'

  return (
    <SettingsPage active="channels" title="메신저" subtitle="Telegram 봇을 연결하면 메신저에서 에이전트와 대화할 수 있습니다.">
      <div className="space-y-6 max-w-[720px]">
        {error && <div className="text-[13px] text-red-500">{error}</div>}

        {!data?.configured && (
          <section className="space-y-2">
            <h2 className={T.section}>Telegram 봇 등록</h2>
            <ol className={`${T.itemDesc} list-decimal pl-5 space-y-0.5`}>
              <li>Telegram 에서 <b>@BotFather</b> 에게 <code>/newbot</code> 을 보내 봇을 만듭니다.</li>
              <li>발급된 봇 토큰을 아래에 붙여 넣습니다. 토큰은 암호화되어 저장됩니다.</li>
              <li>안내되는 링크로 봇을 열어 시작하면 연결이 끝납니다.</li>
            </ol>
            <div className="flex gap-2">
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="123456789:AA…"
                aria-label="봇 토큰"
                autoComplete="off"
                className={inputCls}
              />
              <button className={primaryBtn} disabled={token.trim().length < 20 || connect.isPending} onClick={() => connect.mutate()}>
                {connect.isPending ? '확인 중…' : '등록'}
              </button>
            </div>
          </section>
        )}

        {data?.configured && (
          <section className="p-4 bg-surface-secondary border border-border rounded-lg space-y-3">
            <div className="flex items-center gap-3">
              <Send size={18} className="text-accent-primary" />
              <div className="flex-1 min-w-0">
                <div className={T.itemTitle}>@{data.bot_username}</div>
                <div className={T.meta}>Telegram · 이 봇과는 연결된 본인만 대화할 수 있습니다</div>
              </div>
              {st && <span className={`text-xs px-2 py-0.5 rounded-full ${st.cls}`}>{st.text}</span>}
            </div>
            {data.last_error && <div className="text-[13px] text-red-500">{data.last_error}</div>}

            {showCode && (
              <div className="rounded-[var(--radius-md)] bg-surface-tertiary p-3 space-y-1.5">
                <div className={T.itemDesc}>
                  아래 링크를 열어 <b>시작</b>을 누르거나, 봇에게 <code>/start {issued!.pair_code}</code> 를 보내세요. 10분 안에 한 번만 쓸 수 있습니다.
                </div>
                {issued!.pair_url && (
                  <a href={issued!.pair_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[13px] text-accent-primary">
                    Telegram 에서 열기 <ExternalLink size={13} />
                  </a>
                )}
              </div>
            )}
            {data.status === 'pending' && !showCode && (
              <div className={T.itemDesc}>연결 코드가 없거나 만료되었습니다. 새 코드를 발급하세요.</div>
            )}

            <label className={`${T.itemDesc} flex items-center gap-2 cursor-pointer`}>
              <input type="checkbox" checked={data.notify_schedules} onChange={(e) => notify.mutate(e.target.checked)} />
              예약 작업 결과를 Telegram 으로도 받기
            </label>

            <div className="flex flex-wrap gap-2">
              <button className={primaryBtn} disabled={newCode.isPending} onClick={() => newCode.mutate()}>
                {data.status === 'connected' ? '다른 계정으로 다시 연결' : '새 연결 코드'}
              </button>
              <button
                className="px-4 py-2 rounded-full border border-border bg-transparent text-[14px] text-content-primary cursor-pointer hover:bg-surface-hover"
                onClick={() => toggle.mutate(!data.enabled)}
              >
                {data.enabled ? '일시 중지' : '다시 시작'}
              </button>
              <button
                className="px-4 py-2 rounded-full border border-border bg-transparent text-[14px] text-red-500 cursor-pointer hover:bg-surface-hover"
                onClick={() => { if (window.confirm('봇 연결을 해제할까요? 토큰이 삭제됩니다.')) remove.mutate() }}
              >
                연결 해제
              </button>
            </div>
          </section>
        )}

        <section className="space-y-1">
          <h2 className={T.section}>사용 안내</h2>
          <ul className={`${T.itemDesc} list-disc pl-5 space-y-0.5`}>
            <li><code>/new</code> 새 대화 · <code>/stop</code> 실행 중단 · <code>/status</code> 상태</li>
            <li>Telegram 에서 시작한 대화는 대화 목록에도 나타나며, 사용자 공용 샌드박스를 함께 씁니다.</li>
            <li>코드 실행·파일 변경·MCP·브라우저 도구는 실행 전에 Telegram 에 허용 버튼이 나타납니다 (10분 안에 응답하지 않으면 거부).</li>
            <li>현재는 텍스트 메시지만 지원합니다.</li>
            <li>Telegram 일반 대화는 종단간 암호화가 아닙니다. 비밀번호·키 같은 민감 정보는 보내지 마세요.</li>
          </ul>
        </section>
      </div>
    </SettingsPage>
  )
}

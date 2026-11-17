import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, Check, Loader2, Plus, RefreshCw, Search, X } from 'lucide-react'
import SettingsPage from '../components/skills/SettingsPage'
import { errorText } from '../components/skills/common'
import { headerActionCls, T } from '../components/skills/typography'
import ConnectorIcon from '../components/connectors/ConnectorIcon'
import { connectorsApi, type ConnectorInfo, type ConnectorList } from '../api/connectors'

const chip = (on: boolean) =>
  `px-4 py-1.5 rounded-full text-[14px] border cursor-pointer transition-colors ${
    on ? 'bg-content-primary text-surface-primary border-content-primary' : 'bg-transparent text-content-secondary border-border hover:text-content-primary'
  }`

function ConnectorCard({ c, busy, disabled, onConnect, onDisconnect }: {
  c: ConnectorInfo
  busy: boolean
  disabled: boolean
  onConnect: () => void
  onDisconnect: () => void
}) {
  return (
    <div className="flex items-center gap-3 px-3 py-3 rounded-[var(--radius-lg)] hover:bg-surface-hover transition-colors">
      <ConnectorIcon id={c.id} />
      <div className="min-w-0 flex-1">
        <div className={T.itemTitle}>{c.name}</div>
        <div className={`${T.itemDesc} truncate`}>{c.description}</div>
        <div className={T.meta}>
          {c.category} · {c.connected && c.account_email ? c.account_email : '계정 로그인'}
        </div>
      </div>
      {c.connected ? (
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="flex items-center gap-1 text-[12px] text-accent-done"><Check size={13} /> 연결됨</span>
          <button
            onClick={onDisconnect}
            disabled={busy}
            title="연결 해제"
            aria-label={`${c.name} 연결 해제`}
            className="p-1.5 rounded-md text-content-tertiary hover:text-accent-red bg-transparent border-none cursor-pointer disabled:opacity-40"
          >
            {busy ? <Loader2 size={15} className="animate-spin" /> : <X size={15} />}
          </button>
        </div>
      ) : (
        <button
          onClick={onConnect}
          disabled={busy || disabled}
          title={disabled ? 'Google OAuth 설정이 필요합니다' : `${c.name} 연결`}
          aria-label={`${c.name} 연결`}
          className="p-2 rounded-full text-content-secondary hover:text-content-primary hover:bg-surface-tertiary bg-transparent border-none cursor-pointer disabled:opacity-40 flex-shrink-0"
        >
          {busy ? <Loader2 size={18} className="animate-spin" /> : <Plus size={18} />}
        </button>
      )}
    </div>
  )
}

/** 커넥터: 대화에서 도구로 쓸 외부 서비스를 계정 로그인으로 연결한다. */
export default function ConnectorsPage() {
  const [data, setData] = useState<ConnectorList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('all')
  const [busyId, setBusyId] = useState<string | null>(null)
  const pollRef = useRef<number | null>(null)

  const load = useCallback(async () => {
    try {
      setData(await connectorsApi.list())
      setError(null)
    } catch (e) {
      setError(errorText(e, '커넥터 목록을 불러오지 못했습니다'))
    }
  }, [])

  useEffect(() => {
    load()
    return () => { if (pollRef.current) window.clearInterval(pollRef.current) }
  }, [load])

  // 인증 창이 보내는 완료 알림(postMessage)을 받으면 바로 새로 고친다
  useEffect(() => {
    const onMsg = (e: MessageEvent) => {
      if (e.data?.type === 'connector-connected' || e.data?.type === 'connector-error') {
        if (pollRef.current) window.clearInterval(pollRef.current)
        setBusyId(null)
        load()
      }
    }
    window.addEventListener('message', onMsg)
    return () => window.removeEventListener('message', onMsg)
  }, [load])

  const connect = async (id: string) => {
    setBusyId(id)
    setError(null)
    // 팝업 차단을 피하려고 클릭 직후 빈 창을 먼저 열고, 인증 주소를 받으면 그 창을 이동시킨다
    const w = window.open('', 'connector-auth', 'width=520,height=720')
    try {
      const url = await connectorsApi.connect(id)
      if (w) w.location.href = url
      else window.location.href = url
    } catch (e) {
      w?.close()
      setBusyId(null)
      setError(errorText(e, '연결을 시작하지 못했습니다'))
      return
    }
    // postMessage 를 못 받는 경우(창을 그냥 닫는 등)를 위해 연결 상태를 확인한다: 2초마다, 최대 3분
    let tries = 0
    if (pollRef.current) window.clearInterval(pollRef.current)
    pollRef.current = window.setInterval(async () => {
      tries++
      try {
        const list = await connectorsApi.list()
        setData(list)
        const done = list.connectors.find((c) => c.id === id)?.connected
        if (done || tries > 90 || (w && w.closed && tries > 3)) {
          window.clearInterval(pollRef.current!)
          setBusyId(null)
        }
      } catch {
        /* 다음 주기에 다시 확인한다 */
      }
    }, 2000)
  }

  const disconnect = async (c: ConnectorInfo) => {
    if (!confirm(`${c.name} 연결을 해제할까요?\n에이전트가 더 이상 이 서비스를 쓸 수 없습니다. 연결된 서비스가 하나도 없으면 Google 쪽 허용도 함께 취소됩니다.`)) return
    setBusyId(c.id)
    try {
      await connectorsApi.disconnect(c.id)
      await load()
    } catch (e) {
      setError(errorText(e, '연결을 해제하지 못했습니다'))
    } finally {
      setBusyId(null)
    }
  }

  const categories = useMemo(() => [...new Set((data?.connectors ?? []).map((c) => c.category))], [data])
  const visible = useMemo(
    () =>
      (data?.connectors ?? []).filter(
        (c) =>
          (category === 'all' || c.category === category) &&
          (c.name + c.description).toLowerCase().includes(query.trim().toLowerCase()),
      ),
    [data, category, query],
  )
  const connected = visible.filter((c) => c.connected)
  const available = visible.filter((c) => !c.connected)

  return (
    <SettingsPage
      active="connectors"
      title="커넥터"
      subtitle="연결한 서비스는 대화에서 도구로 바로 쓸 수 있습니다."
      actions={
        <button onClick={load} className={headerActionCls}>
          <RefreshCw size={14} /> 새로고침
        </button>
      }
    >
      {data && !data.configured && (
        <div className="mb-4 rounded-[var(--radius-lg)] border border-accent-amber/40 bg-accent-amber/10 px-4 py-3 text-[13px] text-content-primary">
          <div className="flex items-center gap-2 font-medium"><AlertTriangle size={15} className="text-accent-amber" /> Google OAuth 설정이 필요합니다</div>
          <p className="mt-1 text-content-secondary">
            서버 환경변수 <code>GOOGLE_OAUTH_CLIENT_ID</code>, <code>GOOGLE_OAUTH_CLIENT_SECRET</code> 을 설정하고 Google Cloud 콘솔의 OAuth 클라이언트(웹 애플리케이션)
            승인된 리디렉션 URI 에 <code className="break-all">{data.redirect_uri}</code> 를 등록하세요. 설정 후 서버를 재시작하면 연결할 수 있습니다.
          </p>
        </div>
      )}
      {error && <p className="mb-3 text-sm text-accent-red whitespace-pre-wrap break-words">{error}</p>}

      <div className="relative">
        <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-content-tertiary" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="커넥터 검색"
          className="w-full pl-11 pr-4 py-2.5 rounded-[var(--radius-lg)] border border-border bg-surface-primary text-[14px] text-content-primary focus:outline-none focus:border-accent-primary"
        />
      </div>
      <div className="flex flex-wrap gap-2 mt-4">
        <button className={chip(category === 'all')} onClick={() => setCategory('all')}>전체 분류</button>
        {categories.map((cat) => (
          <button key={cat} className={chip(category === cat)} onClick={() => setCategory(cat)}>{cat}</button>
        ))}
      </div>

      {!data ? (
        <div className="py-12 text-center text-sm text-content-tertiary"><Loader2 size={14} className="inline animate-spin mr-1" /> 불러오는 중...</div>
      ) : visible.length === 0 ? (
        <div className="py-12 text-center text-sm text-content-muted">검색 결과가 없습니다.</div>
      ) : (
        <>
          {connected.length > 0 && (
            <section className="mt-6">
              <h2 className="text-[14px] font-semibold text-content-primary mb-2">연결됨</h2>
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-x-6">
                {connected.map((c) => (
                  <ConnectorCard key={c.id} c={c} busy={busyId === c.id} disabled={false} onConnect={() => connect(c.id)} onDisconnect={() => disconnect(c)} />
                ))}
              </div>
            </section>
          )}
          {available.length > 0 && (
            <section className="mt-6">
              <h2 className="text-[14px] font-semibold text-content-primary mb-2">바로 연결</h2>
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-x-6">
                {available.map((c) => (
                  <ConnectorCard key={c.id} c={c} busy={busyId === c.id} disabled={!data.configured} onConnect={() => connect(c.id)} onDisconnect={() => disconnect(c)} />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </SettingsPage>
  )
}

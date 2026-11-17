import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'
import { Bot, Loader2, User } from 'lucide-react'
import { shareApi, type SharedConversation } from '../api/share'
import WidgetRenderer from '../components/widgets/WidgetRenderer'
import { formatKoreanDateTime } from '../utils/time'

/** 공유된 대화를 로그인 없이 읽는 페이지 (읽기 전용). 공유 시점에 복사된 내용만 보인다. */
export default function SharedChatPage() {
  const { token = '' } = useParams()
  const [data, setData] = useState<SharedConversation | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    shareApi.read(token).then(
      (r) => !cancelled && setData(r.data),
      (e) => !cancelled && setErr(e?.response?.status === 429 ? '요청이 너무 많습니다. 잠시 후 다시 열어 주세요' : '공유가 해제되었거나 존재하지 않는 링크입니다'),
    )
    return () => { cancelled = true }
  }, [token])

  useEffect(() => {
    // 검색엔진에 노출되지 않게 한다
    const m = document.createElement('meta')
    m.name = 'robots'
    m.content = 'noindex, nofollow'
    document.head.appendChild(m)
    return () => { m.remove() }
  }, [])
  useEffect(() => {
    if (data?.title) document.title = data.title
  }, [data?.title])

  return (
    <div className="min-h-screen bg-surface-primary text-content-primary">
      <header className="border-b border-border">
        <div className="max-w-3xl mx-auto px-4 py-3">
          <h1 className="m-0 text-base font-semibold truncate">{data?.title ?? '공유된 대화'}</h1>
          <p className="m-0 mt-0.5 text-[11px] text-content-muted">
            공유된 대화 (읽기 전용){data?.shared_at && <> · {formatKoreanDateTime(data.shared_at)} 기준</>}
          </p>
        </div>
      </header>
      <main className="max-w-3xl mx-auto px-4 py-6 space-y-5">
        {err ? (
          <div className="py-20 text-center text-sm text-content-secondary">{err}</div>
        ) : !data ? (
          <div className="py-20 flex items-center justify-center text-sm text-content-muted"><Loader2 size={16} className="animate-spin mr-2" /> 불러오는 중...</div>
        ) : (
          data.messages.map((m, i) => (
            <article key={i} className={`flex gap-3 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className="shrink-0 w-7 h-7 rounded-full bg-surface-tertiary flex items-center justify-center text-content-secondary" aria-hidden>
                {m.role === 'user' ? <User size={14} /> : <Bot size={14} />}
              </div>
              <div className={`min-w-0 max-w-[85%] rounded-[var(--radius-lg)] px-3.5 py-2.5 ${m.role === 'user' ? 'bg-accent-primary text-white' : 'bg-surface-secondary border border-border'}`}>
                {m.role === 'assistant' && <WidgetRenderer widgets={m.widgets} />}
                {m.role === 'user' ? (
                  <p className="m-0 text-sm whitespace-pre-wrap break-words">{m.content}</p>
                ) : (
                  // 신뢰할 수 없는 내용이 들어갈 수 있으므로 raw HTML 은 허용하지 않고 sanitize 한다
                  <div className="prose prose-sm max-w-none text-content-primary break-words">
                    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>{m.content}</ReactMarkdown>
                  </div>
                )}
              </div>
            </article>
          ))
        )}
      </main>
    </div>
  )
}

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'

const WIKI_HREF = '#wiki='

/** [[문서 제목]] 을 열 수 있는 링크로 바꾼다. 제목에 맞는 문서가 없으면 링크 없이 제목만 남긴다. */
function resolveWikiLinks(text: string, titles: Map<string, string>): string {
  return text.replace(/\[\[([^\]\n]+)\]\]/g, (_m, raw: string) => {
    const id = titles.get(raw.trim().toLowerCase())
    return id ? `[${raw.trim()}](${WIKI_HREF}${id})` : raw.trim()
  })
}

/** 위키 문서 본문(마크다운) 렌더러. 표·목록·소제목을 읽기 좋게 그리고, [[제목]] 링크는 다른 문서로 이어 준다. */
export default function WikiMarkdown({
  children,
  docs,
  onOpen,
}: {
  children: string
  docs?: { id: string; title: string }[]
  onOpen?: (id: string) => void
}) {
  const body = docs?.length ? resolveWikiLinks(children, new Map(docs.map((d) => [d.title.trim().toLowerCase(), d.id]))) : children
  return (
    <div className="text-sm text-content-primary leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        components={{
          h1: (p) => <h1 className="text-lg font-semibold mt-4 mb-2" {...p} />,
          h2: (p) => <h2 className="text-[15px] font-semibold mt-4 mb-2 pb-1 border-b border-border" {...p} />,
          h3: (p) => <h3 className="text-sm font-semibold mt-3 mb-1.5" {...p} />,
          p: (p) => <p className="my-2" {...p} />,
          ul: (p) => <ul className="list-disc pl-5 my-2 space-y-1" {...p} />,
          ol: (p) => <ol className="list-decimal pl-5 my-2 space-y-1" {...p} />,
          a: ({ href, children: kids, ...rest }) =>
            href?.startsWith(WIKI_HREF) ? (
              <a
                href={href}
                onClick={(e) => {
                  e.preventDefault()
                  onOpen?.(href.slice(WIKI_HREF.length))
                }}
                className="text-accent-primary underline cursor-pointer"
              >
                {kids}
              </a>
            ) : (
              <a className="text-accent-primary underline break-all" href={href} target="_blank" rel="noopener noreferrer" {...rest}>
                {kids}
              </a>
            ),
          code: (p) => <code className="px-1 py-0.5 rounded bg-surface-tertiary text-[12px] font-mono" {...p} />,
          pre: (p) => <pre className="my-2 p-3 rounded-[var(--radius-md)] bg-surface-tertiary overflow-x-auto text-[12px]" {...p} />,
          blockquote: (p) => <blockquote className="my-2 pl-3 border-l-4 border-accent-primary text-content-secondary" {...p} />,
          table: (p) => (
            <div className="overflow-x-auto my-3">
              <table className="min-w-full text-[13px] border border-border rounded-[var(--radius-md)]" {...p} />
            </div>
          ),
          thead: (p) => <thead className="bg-surface-tertiary" {...p} />,
          th: (p) => <th className="px-3 py-1.5 text-left border-b border-border font-semibold" {...p} />,
          td: (p) => <td className="px-3 py-1.5 border-b border-border" {...p} />,
        }}
      >
        {body}
      </ReactMarkdown>
    </div>
  )
}

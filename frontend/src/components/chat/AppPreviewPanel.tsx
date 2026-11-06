import { useState } from 'react'
import { ExternalLink, RefreshCw } from 'lucide-react'
import type { DeployedAppRef } from './deployedApp'

/** 배포된 웹앱을 iframe 으로 보여 준다. 컨테이너가 꺼져 있었다면 앱의 '시작 중' 화면이 보였다가 준비되면 스스로 새로고침된다. */
export default function AppPreviewPanel({ app }: { app: DeployedAppRef }) {
  const [nonce, setNonce] = useState(0)
  const shown = app.url.replace(/\?t=[^&]*/, '?t=…')
  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-1.5 px-3 py-2 border-b border-border bg-surface-secondary">
        <span className="flex-1 min-w-0 truncate text-xs text-content-secondary" title={shown}>{shown}</span>
        <button onClick={() => setNonce((n) => n + 1)} title="새로고침" aria-label="새로고침" className="p-1.5 text-content-muted hover:text-content-primary border-none bg-transparent cursor-pointer"><RefreshCw size={13} /></button>
        <a href={app.url} target="_blank" rel="noreferrer" title="새 창에서 열기" aria-label="새 창에서 열기" className="p-1.5 text-content-muted hover:text-content-primary"><ExternalLink size={13} /></a>
      </div>
      <iframe
        key={`${app.url}-${nonce}`}
        src={app.url}
        title={app.name}
        className="flex-1 w-full border-0 bg-white"
        sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals allow-downloads"
        referrerPolicy="no-referrer"
      />
    </div>
  )
}

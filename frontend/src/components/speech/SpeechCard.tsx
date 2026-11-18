import { useEffect, useState } from 'react'
import { Download, Loader2, Volume2 } from 'lucide-react'
import { sandboxApi } from '../../api/sandbox'
import type { AgentStepData } from '../../types/chat'

export interface SpeechAudio {
  path: string
  voice: string
  seconds: number
  bytes: number
}

export interface SpeechGroup {
  preview: boolean
  audio: SpeechAudio[]
  warnings: string[]
}

/** generate_speech 의 성공한 tool_result 에서 재생할 음성을 꺼낸다 (실시간·저장된 메시지 공통). 오류 문장 등 JSON 이 아닌 결과는 무시한다. */
export function extractSpeech(steps: AgentStepData[] | undefined): SpeechGroup[] {
  const out: SpeechGroup[] = []
  for (const s of steps ?? []) {
    if (s.type !== 'tool_result' || s.tool !== 'generate_speech' || typeof s.output !== 'string') continue
    try {
      const j = JSON.parse(s.output)
      if (j?.ok && Array.isArray(j.audio) && j.audio.length > 0) out.push({ preview: !!j.preview, audio: j.audio as SpeechAudio[], warnings: Array.isArray(j.warnings) ? j.warnings : [] })
    } catch {
      // 무시
    }
  }
  return out
}

function fmtSeconds(s: number): string {
  const m = Math.floor(s / 60)
  return m > 0 ? `${m}분 ${Math.round(s % 60)}초` : `${s.toFixed(1)}초`
}

/** 인증이 필요한 sandbox 파일이라 <audio src> 로 바로 부를 수 없다: blob 으로 받아 재생한다 */
function AudioItem({ item, conversationId }: { item: SpeechAudio; conversationId: string }) {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null
    setUrl(null)
    setError(false)
    sandboxApi.fetchArtifactBlob(item.path, true, conversationId).then(
      (res) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(new Blob([res.data], { type: item.path.toLowerCase().endsWith('.mp3') ? 'audio/mpeg' : 'audio/wav' }))  // 서버는 다운로드용 형식으로 주므로 재생용 형식을 지정한다
        setUrl(objectUrl)
      },
      () => !cancelled && setError(true),
    )
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [item.path, conversationId])

  const fileName = item.path.split('/').pop() ?? 'speech.mp3'
  return (
    <div className="flex items-center gap-3 flex-wrap">
      <span className="min-w-[56px] px-2 py-0.5 rounded-full text-[11px] font-medium text-center bg-accent-primary/15 text-accent-primary" aria-label={`목소리 ${item.voice}`}>{item.voice}</span>
      <span className="text-[11px] text-content-tertiary w-14">{fmtSeconds(item.seconds)}</span>
      {error ? <span role="alert" className="text-xs text-accent-red">음성 파일을 불러오지 못했습니다 (작업공간이 종료되었을 수 있습니다)</span>
        : !url ? <span className="flex items-center gap-1.5 text-xs text-content-muted"><Loader2 size={12} className="animate-spin" /> 불러오는 중...</span>
        : <>
            <audio src={url} controls preload="metadata" aria-label={`${item.voice} 목소리 재생`} className="h-8 flex-1 min-w-[220px] max-w-[420px]" />
            <a href={url} download={fileName} title="다운로드" aria-label={`${item.voice} 음성 다운로드`} className="p-1 text-content-tertiary hover:text-content-primary"><Download size={14} /></a>
          </>}
    </div>
  )
}

/** 채팅의 음성 재생 카드. 미리듣기(두 목소리)면 나란히 들어 보고 고르도록 안내한다. */
export default function SpeechCard({ group, conversationId }: { group: SpeechGroup; conversationId: string }) {
  return (
    <section aria-label={group.preview ? '목소리 미리듣기' : '생성된 음성'} className="my-3 p-3 rounded-xl border border-border bg-surface-secondary space-y-2">
      <div className="flex items-center gap-1.5 text-xs font-medium text-content-secondary">
        <Volume2 size={14} aria-hidden /> {group.preview ? '목소리 미리듣기 — 두 목소리를 들어 보고 골라 주세요' : '생성된 음성'}
      </div>
      {group.audio.map((a) => <AudioItem key={a.path} item={a} conversationId={conversationId} />)}
      {group.warnings.map((w, i) => <p key={i} className="m-0 text-[11px] text-accent-amber">{w}</p>)}
      {!group.preview && <p className="m-0 text-[11px] text-content-tertiary truncate" title={group.audio[0].path}>{group.audio[0].path}</p>}
    </section>
  )
}

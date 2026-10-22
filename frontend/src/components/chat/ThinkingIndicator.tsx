import { useEffect, useState } from 'react'
import { useAgentStore } from '../../store/agentStore'
import { statusText } from './pendingStep'

// 토큰이 이만큼(ms) 안에 도착했으면 글이 흐르는 중이므로 표시를 숨긴다
const FLOWING_MS = 1000

/**
 * 에이전트 응답 맨 아래에 붙는 "실행 중" 표시: 점 세 개 애니메이션 + 현재 상태 문구.
 * 첫 응답 전, 도구 실행 중, 최종 답변을 쓰기 전처럼 화면이 멈춘 듯 보이는 구간을 메운다.
 * `settled`: 화면의 글자(타이핑 애니메이션)가 수신한 내용을 모두 따라잡았는지.
 */
export default function ThinkingIndicator({ settled }: { settled: boolean }) {
  const steps = useAgentStore((s) => s.currentSteps)
  const streamed = useAgentStore((s) => s.streamingContent)
  const [flowing, setFlowing] = useState(false)

  useEffect(() => {
    if (!streamed) return
    setFlowing(true)
    const t = setTimeout(() => setFlowing(false), FLOWING_MS)
    return () => clearTimeout(t)
  }, [streamed])

  if (flowing || !settled) return null
  return (
    <div role="status" aria-live="polite" className="thinking-indicator mt-2 flex items-center gap-2 text-[13px] text-content-secondary">
      <span className="thinking-dots" aria-hidden>
        <span />
        <span />
        <span />
      </span>
      <span>{statusText(steps)}</span>
    </div>
  )
}

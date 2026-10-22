import type { AgentStep } from '../../types/agent'
import { TOOL_LABELS } from './StepProgressItem'

/**
 * 아직 결과(tool_result)가 오지 않은 가장 안쪽(마지막) 도구 호출을 찾는다.
 * 호출/결과를 도구 이름으로 짝지어 스택처럼 처리하므로, 팀원 위임 안에서 웹 검색이 돌고 있으면 웹 검색이 반환된다.
 */
export function findPendingCall(steps: AgentStep[]): AgentStep | null {
  const pending: AgentStep[] = []
  for (const s of steps) {
    if (s.type === 'tool_call') {
      pending.push(s)
    } else if (s.type === 'tool_result') {
      for (let i = pending.length - 1; i >= 0; i--) {
        if (pending[i].tool === s.tool) {
          pending.splice(i, 1)
          break
        }
      }
    }
  }
  return pending.length ? pending[pending.length - 1] : null
}

/** 실행 중 표시줄에 보여 줄 현재 상태 문구 */
export function statusText(steps: AgentStep[]): string {
  const call = findPendingCall(steps)
  if (call) {
    if (call.tool === 'narrate') {
      const msg = (call.input as { message?: string } | undefined)?.message
      if (typeof msg === 'string' && msg.trim()) return msg.trim().slice(0, 60)
    }
    if (call.tool === 'form_ask_user') return '사용자의 답변을 기다리는 중…'
    const label = TOOL_LABELS[call.tool ?? ''] ?? call.tool
    if (label) return `${label} 중…`
  }
  return steps.length > 0 ? '답변을 정리하는 중…' : '생각하는 중…'
}

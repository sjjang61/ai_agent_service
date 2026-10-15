import type { AgentStepData } from '../../types/chat'

/**
 * 워크플로우 다이어그램으로 표시할 가치가 있는 패턴인지 탐지
 *
 * 자동 표시 조건:
 * 1. tool_call이 3개 이상
 * 2. thought → tool_call → tool_result 패턴이 2회 이상 반복
 */
export function shouldShowWorkflow(steps: AgentStepData[]): boolean {
  if (!steps || steps.length === 0) return false

  // 조건 1: tool_call이 3개 이상
  const toolCalls = steps.filter((s) => s.type === 'tool_call')
  if (toolCalls.length >= 3) return true

  // 조건 2: thought → tool_call → tool_result 패턴 반복
  let patternCount = 0
  for (let i = 0; i < steps.length - 2; i++) {
    if (
      steps[i].type === 'thought' &&
      steps[i + 1].type === 'tool_call' &&
      steps[i + 2].type === 'tool_result'
    ) {
      patternCount++
    }
  }

  return patternCount >= 2
}

/**
 * 워크플로우의 복잡도를 계산 (레이아웃 최적화용)
 */
export function calculateWorkflowComplexity(steps: AgentStepData[]): 'simple' | 'medium' | 'complex' {
  const stepCount = steps.length

  if (stepCount <= 5) return 'simple'
  if (stepCount <= 10) return 'medium'
  return 'complex'
}

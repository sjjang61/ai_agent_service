export interface UsageSummary {
  total_requests: number
  total_input_tokens: number
  total_output_tokens: number
  total_tokens: number
  /** 예상 비용(USD, 캐시 할인 미반영). 단가를 모르는 모델의 사용량은 빠진다 */
  cost_usd: number
  cost_incomplete: boolean
}

export interface DailyUsage {
  date: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  /** 예상 비용(USD, 캐시 할인 미반영). 단가를 모르는 모델의 사용량은 빠진다 */
  cost_usd: number
  cost_incomplete: boolean
  request_count: number
}

export interface UserUsage {
  user_id: string
  email: string
  display_name: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  /** 예상 비용(USD, 캐시 할인 미반영). 단가를 모르는 모델의 사용량은 빠진다 */
  cost_usd: number
  cost_incomplete: boolean
  request_count: number
}

export interface ModelUsage {
  llm_provider: string
  model_name: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  /** 예상 비용(USD, 캐시 할인 미반영). 단가를 모르는 모델의 사용량은 빠진다 */
  cost_usd: number
  cost_incomplete: boolean
  request_count: number
}

export interface SessionUsage {
  conversation_id: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  /** 예상 비용(USD, 캐시 할인 미반영). 단가를 모르는 모델의 사용량은 빠진다 */
  cost_usd: number
  cost_incomplete: boolean
  request_count: number
}

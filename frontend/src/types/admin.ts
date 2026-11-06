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

export interface PriceRow {
  model: string
  input: number
  cached_input: number | null
  output: number
  /** default: 코드 기본 표 / page: 가격 페이지에서 갱신 / custom: 설정(MODEL_PRICES_JSON) */
  source: 'default' | 'page' | 'custom'
}

export interface PricingState {
  url: string
  default_url: string
  last_updated_at: string | null
  last_status: string | null
  last_method: 'structured' | 'table' | 'llm' | null
  last_count: number
  prices: PriceRow[]
}

export interface PricingRefreshResult {
  method: string
  model_count: number
  added: string[]
  changed: { model: string; old: { input: number; output: number }; new: { input: number; output: number } }[]
  updated_at: string
}

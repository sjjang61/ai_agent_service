export interface UsageSummary {
  total_requests: number
  total_input_tokens: number
  total_output_tokens: number
  total_tokens: number
}

export interface DailyUsage {
  date: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  request_count: number
}

export interface UserUsage {
  user_id: string
  email: string
  display_name: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  request_count: number
}

export interface ModelUsage {
  llm_provider: string
  model_name: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  request_count: number
}

export interface SessionUsage {
  conversation_id: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  request_count: number
}

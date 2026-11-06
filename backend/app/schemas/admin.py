from pydantic import BaseModel


class UsageSummaryResponse(BaseModel):
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    cost_usd: float = 0.0  # 예상 비용 (USD, 캐시 할인 미반영)
    cost_incomplete: bool = False  # 단가를 모르는 모델이 섞여 있어 실제보다 적게 나왔을 수 있음


class DailyUsageResponse(BaseModel):
    date: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float = 0.0  # 예상 비용 (USD, 캐시 할인 미반영)
    cost_incomplete: bool = False  # 단가를 모르는 모델이 섞여 있어 실제보다 적게 나왔을 수 있음
    request_count: int


class UserUsageResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float = 0.0  # 예상 비용 (USD, 캐시 할인 미반영)
    cost_incomplete: bool = False  # 단가를 모르는 모델이 섞여 있어 실제보다 적게 나왔을 수 있음
    request_count: int


class ModelUsageResponse(BaseModel):
    llm_provider: str
    model_name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float = 0.0  # 예상 비용 (USD, 캐시 할인 미반영)
    cost_incomplete: bool = False  # 단가를 모르는 모델이 섞여 있어 실제보다 적게 나왔을 수 있음
    request_count: int


class SessionUsageResponse(BaseModel):
    conversation_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float = 0.0  # 예상 비용 (USD, 캐시 할인 미반영)
    cost_incomplete: bool = False  # 단가를 모르는 모델이 섞여 있어 실제보다 적게 나왔을 수 있음
    request_count: int

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


class PriceRow(BaseModel):
    model: str
    input: float
    cached_input: float | None = None
    output: float
    source: str  # default | page | custom


class PricingState(BaseModel):
    url: str
    default_url: str
    last_updated_at: str | None = None
    last_status: str | None = None
    last_method: str | None = None  # structured | table | llm
    last_count: int = 0
    prices: list[PriceRow] = []


class PricingUrlRequest(BaseModel):
    url: str


class PricingRefreshResult(BaseModel):
    method: str
    model_count: int
    added: list[str] = []
    changed: list[dict] = []
    updated_at: str

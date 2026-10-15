from pydantic import BaseModel


class UsageSummaryResponse(BaseModel):
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int


class DailyUsageResponse(BaseModel):
    date: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_count: int


class UserUsageResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_count: int


class ModelUsageResponse(BaseModel):
    llm_provider: str
    model_name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_count: int


class SessionUsageResponse(BaseModel):
    conversation_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_count: int

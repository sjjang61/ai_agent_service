from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

ScheduleType = Literal["once", "interval", "daily", "weekdays", "weekly", "monthly"]


def _to_utc_naive(v: Optional[datetime]) -> Optional[datetime]:
    """클라이언트가 보낸 시각을 UTC naive 로 맞춘다 (시간대 정보가 없으면 UTC 로 본다)."""
    if v is None:
        return None
    if v.tzinfo is not None:
        v = v.astimezone(timezone.utc).replace(tzinfo=None)
    return v


class TaskInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=4000)
    schedule_type: ScheduleType
    schedule_time: Optional[str] = None  # "HH:MM" (현지)
    weekdays: Optional[List[int]] = None  # 0=월 … 6=일
    day_of_month: Optional[int] = None
    interval_hours: Optional[int] = None
    run_at: Optional[datetime] = None
    timezone: str = "Asia/Seoul"
    new_conversation_each_run: bool = False
    allow_mcp: bool = False
    allow_browser: bool = False
    llm_provider: Optional[str] = None
    model_name: Optional[str] = None

    @field_validator("run_at")
    @classmethod
    def _run_at(cls, v):
        return _to_utc_naive(v)

    @field_validator("name", "prompt")
    @classmethod
    def _strip(cls, v: str):
        v = v.strip()
        if not v:
            raise ValueError("비어 있을 수 없습니다")
        return v


class TaskUpdate(BaseModel):
    """부분 수정. 보낸 필드만 바꾸고, 일정 관련 필드가 바뀌면 다음 실행 시각을 다시 계산한다."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    prompt: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    schedule_type: Optional[ScheduleType] = None
    schedule_time: Optional[str] = None
    weekdays: Optional[List[int]] = None
    day_of_month: Optional[int] = None
    interval_hours: Optional[int] = None
    run_at: Optional[datetime] = None
    timezone: Optional[str] = None
    new_conversation_each_run: Optional[bool] = None
    allow_mcp: Optional[bool] = None
    allow_browser: Optional[bool] = None
    llm_provider: Optional[str] = None
    model_name: Optional[str] = None

    @field_validator("run_at")
    @classmethod
    def _run_at(cls, v):
        return _to_utc_naive(v)


class EnabledRequest(BaseModel):
    enabled: bool


class RunResponse(BaseModel):
    id: str
    task_id: str
    status: str
    trigger: str
    scheduled_for: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    conversation_id: Optional[str] = None
    summary: Optional[str] = None
    error: Optional[str] = None
    unread: bool = False


class TaskResponse(BaseModel):
    id: str
    name: str
    prompt: str
    schedule_type: str
    schedule_time: Optional[str] = None
    weekdays: Optional[List[int]] = None
    day_of_month: Optional[int] = None
    interval_hours: Optional[int] = None
    run_at: Optional[datetime] = None
    timezone: str
    schedule_text: str
    # active(예정) | paused(일시중지) | auto_paused(연속 실패로 자동 중지) | completed(한 번 실행 완료)
    status: str
    enabled: bool
    running: bool = False
    conversation_id: Optional[str] = None
    new_conversation_each_run: bool
    allow_mcp: bool
    allow_browser: bool
    llm_provider: Optional[str] = None
    model_name: Optional[str] = None
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    last_status: Optional[str] = None
    consecutive_failures: int = 0
    unread_count: int = 0
    last_run: Optional[RunResponse] = None
    created_at: Optional[datetime] = None


class RunStarted(BaseModel):
    run_id: str
    status: str


class UnreadCount(BaseModel):
    count: int

from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


MemoryCategory = Literal["preference", "fact", "instruction", "general"]
MemorySource = Literal["manual", "auto_extracted", "agent"]
# semantic: 안정된 사실 / episodic: 특정 시점의 사건·해결 사례 / procedural: 앞으로 따를 작업 방식
MemoryType = Literal["semantic", "episodic", "procedural"]


class EpisodeDetail(BaseModel):
    """에피소드(사례) 기억의 구조: 상황 → 해결 → 결과"""

    situation: str = Field(default="", max_length=1000)
    resolution: str = Field(default="", max_length=1000)
    outcome: str = Field(default="", max_length=1000)


def default_type_for(category: str) -> str:
    """memory_type 이 없는 요청(구 클라이언트·에이전트 도구)은 category 로 유추한다."""
    return "procedural" if category == "instruction" else "semantic"


class MemoryCreate(BaseModel):
    """Schema for creating a new memory."""

    memory_type: Optional[MemoryType] = None  # None 이면 category 로 유추
    occurred_at: Optional[datetime] = None  # episodic 전용 (UTC)
    detail: Optional[EpisodeDetail] = None  # episodic 전용
    category: MemoryCategory = "general"
    key: str = Field(..., min_length=1, max_length=200)
    value: str = Field(..., min_length=1)
    tags: List[str] = []
    importance: int = Field(default=5, ge=1, le=10)


class MemoryUpdate(BaseModel):
    """Schema for updating an existing memory."""

    category: Optional[MemoryCategory] = None
    memory_type: Optional[MemoryType] = None
    occurred_at: Optional[datetime] = None
    detail: Optional[EpisodeDetail] = None
    value: Optional[str] = None
    tags: Optional[List[str]] = None
    importance: Optional[int] = Field(default=None, ge=1, le=10)
    is_active: Optional[bool] = None


class MemoryResponse(BaseModel):
    """Schema for memory response."""

    id: str
    category: str
    memory_type: str = "semantic"
    occurred_at: Optional[datetime] = None
    detail: Optional[EpisodeDetail] = None
    key: str
    value: str
    tags: List[str]
    source: str
    importance: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MemorySearchParams(BaseModel):
    """Schema for memory search parameters."""

    query: Optional[str] = None  # keyword search in key/value
    category: Optional[MemoryCategory] = None
    memory_type: Optional[MemoryType] = None
    tags: Optional[List[str]] = None
    min_importance: Optional[int] = Field(default=None, ge=1, le=10)
    limit: int = Field(default=50, le=200)
    offset: int = 0


class ShortTermMemoryResponse(BaseModel):
    """Schema for short-term memory response."""

    conversation_id: str
    memories: dict

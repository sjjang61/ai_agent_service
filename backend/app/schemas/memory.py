from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


MemoryCategory = Literal["preference", "fact", "instruction", "general"]
MemorySource = Literal["manual", "auto_extracted", "agent"]


class MemoryCreate(BaseModel):
    """Schema for creating a new memory."""

    category: MemoryCategory = "general"
    key: str = Field(..., min_length=1, max_length=200)
    value: str = Field(..., min_length=1)
    tags: List[str] = []
    importance: int = Field(default=5, ge=1, le=10)


class MemoryUpdate(BaseModel):
    """Schema for updating an existing memory."""

    category: Optional[MemoryCategory] = None
    value: Optional[str] = None
    tags: Optional[List[str]] = None
    importance: Optional[int] = Field(default=None, ge=1, le=10)
    is_active: Optional[bool] = None


class MemoryResponse(BaseModel):
    """Schema for memory response."""

    id: str
    category: str
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
    tags: Optional[List[str]] = None
    min_importance: Optional[int] = Field(default=None, ge=1, le=10)
    limit: int = Field(default=50, le=200)
    offset: int = 0


class ShortTermMemoryResponse(BaseModel):
    """Schema for short-term memory response."""

    conversation_id: str
    memories: dict

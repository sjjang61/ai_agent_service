"""Pydantic schemas for Wiki entries."""

from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


WikiCategory = Literal["general", "work", "learning", "reference"]


class WikiEntryCreate(BaseModel):
    """Schema for creating a new wiki entry."""

    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    category: WikiCategory = "general"
    tags: List[str] = []
    source_message_id: Optional[str] = None
    source_conversation_id: Optional[str] = None


class WikiEntryUpdate(BaseModel):
    """Schema for updating an existing wiki entry."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    category: Optional[WikiCategory] = None
    tags: Optional[List[str]] = None


class WikiEntryResponse(BaseModel):
    """Schema for wiki entry response."""

    id: str
    user_id: str
    title: str
    content: str
    category: str
    tags: List[str]
    source_message_id: Optional[str]
    source_conversation_id: Optional[str]
    created_at: datetime
    updated_at: datetime


class WikiSearchParams(BaseModel):
    """Schema for wiki search parameters."""

    query: Optional[str] = None  # Keyword search in title/content
    category: Optional[WikiCategory] = None
    tags: Optional[List[str]] = None
    limit: int = Field(default=50, le=200)
    offset: int = 0

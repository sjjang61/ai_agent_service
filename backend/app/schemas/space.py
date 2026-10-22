from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SpaceInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class SpaceResponse(BaseModel):
    id: str
    name: str
    page_count: int = 0


class PageCreate(BaseModel):
    title: str = Field(default="", max_length=200)
    content: str = Field(default="", max_length=500_000)
    space_id: Optional[str] = None


class PageUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    content: Optional[str] = Field(default=None, max_length=500_000)
    is_favorite: Optional[bool] = None
    space_id: Optional[str] = None
    clear_space: bool = False  # space_id 를 비우려면 true


class PageSummary(BaseModel):
    id: str
    title: str
    snippet: str = ""
    space_id: Optional[str] = None
    is_favorite: bool
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class PageResponse(PageSummary):
    content: str

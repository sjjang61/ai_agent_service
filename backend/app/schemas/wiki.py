"""Pydantic schemas for Wiki entries."""

from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


WikiCategory = Literal["general", "work", "learning", "reference"]


class WikiLinkRef(BaseModel):
    id: str
    title: str


class WikiEntryCreate(BaseModel):
    """Schema for creating a new wiki entry."""

    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    category: WikiCategory = "general"
    tags: List[str] = []
    summary: Optional[str] = Field(None, max_length=500)
    source_text: Optional[str] = None
    links: List[str] = []
    source_message_id: Optional[str] = None
    source_conversation_id: Optional[str] = None


class WikiEntryUpdate(BaseModel):
    """Schema for updating an existing wiki entry."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    category: Optional[WikiCategory] = None
    tags: Optional[List[str]] = None
    summary: Optional[str] = Field(None, max_length=500)
    source_text: Optional[str] = None
    links: Optional[List[str]] = None


class WikiEntryResponse(BaseModel):
    """Schema for wiki entry response."""

    id: str
    user_id: str
    title: str
    content: str
    category: str
    tags: List[str]
    summary: Optional[str] = None
    source_text: Optional[str] = None
    links: List[WikiLinkRef] = []  # 이 문서가 연결한 문서
    backlinks: List[WikiLinkRef] = []  # 이 문서를 연결한 문서
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


class WikiDraftRequest(BaseModel):
    """선택한 텍스트를 위키 문서로 정리해 달라는 요청."""

    selected_text: str = Field(..., min_length=1, max_length=20000)
    allow_merge: bool = True  # false 면 같은 주제의 문서가 있어도 합치지 않고 새 문서로 정리한다


class WikiDraftResponse(BaseModel):
    title: str
    summary: str
    content: str
    category: WikiCategory = "general"
    tags: List[str] = []
    merge_into: Optional[WikiLinkRef] = None  # 비슷한 주제의 기존 문서가 있어 그 문서에 합친 결과일 때
    related: List[WikiLinkRef] = []  # 관련 있는 기존 문서


class WikiMergeRequest(BaseModel):
    """기존 문서에 새 내용을 합친 결과를 반영한다 (POST /wiki/{id}/merge)."""

    content: str = Field(..., min_length=1)
    summary: Optional[str] = Field(None, max_length=500)
    tags: List[str] = []
    new_source_text: Optional[str] = None  # 이번에 합친 원문. 기존 원문 뒤에 이어 붙인다
    add_links: List[str] = []


class WikiLintIssue(BaseModel):
    type: Literal["duplicate", "stale", "orphan", "broken_link", "no_summary"]
    message: str
    entries: List[WikiLinkRef]


class WikiLintReport(BaseModel):
    total: int
    issues: List[WikiLintIssue]

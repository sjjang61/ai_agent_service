"""Wiki management API endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.wiki import (
    WikiEntryCreate,
    WikiEntryUpdate,
    WikiEntryResponse,
    WikiSearchParams,
    WikiDraftRequest,
    WikiDraftResponse,
    WikiLinkRef,
    WikiLintReport,
    WikiMergeRequest,
)
from app.services.wiki_service import WikiService

router = APIRouter()


def _to_response(entry, graph=None) -> WikiEntryResponse:
    """Convert WikiEntry model to response schema. graph = WikiService.link_graph 결과 (연결·역링크 제목을 채운다)."""
    links, backlinks = [], []
    if graph:
        titles, out, back = graph
        links = [WikiLinkRef(id=i, title=titles[i]) for i in out.get(entry.id, [])]
        backlinks = [WikiLinkRef(id=i, title=titles[i]) for i in back.get(entry.id, [])]
    return WikiEntryResponse(
        id=entry.id,
        user_id=entry.user_id,
        title=entry.title,
        content=entry.content,
        category=entry.category,
        tags=entry.tags or [],
        summary=entry.summary,
        source_text=entry.source_text,
        links=links,
        backlinks=backlinks,
        source_message_id=entry.source_message_id,
        source_conversation_id=entry.source_conversation_id,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.get("/", response_model=List[WikiEntryResponse])
async def list_wiki_entries(
    query: Optional[str] = Query(None, description="Search keyword"),
    category: Optional[str] = Query(None),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """List user's wiki entries with optional filtering."""
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    params = WikiSearchParams(
        query=query,
        category=category,
        tags=tag_list,
        limit=limit,
        offset=offset,
    )

    entries = await WikiService.list_entries(current_user.id, params, db)
    graph = await WikiService.link_graph(current_user.id, db)
    return [_to_response(e, graph) for e in entries]


@router.post("/draft", response_model=WikiDraftResponse)
async def draft_wiki_entry(
    data: WikiDraftRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """선택한 텍스트를 LLM 이 위키 문서(제목·요약·정리된 본문·카테고리·태그)로 정리한다. 저장은 하지 않는다.
    기존 문서 중 같은 주제가 있으면 그 문서에 합친 결과(merge_into)를, 관련 문서가 있으면 [[링크]]와 related 를 함께 준다."""
    from app.schemas.wiki import WikiSearchParams
    from app.services.wiki_draft import MAX_CANDIDATES, draft_article

    existing = await WikiService.list_entries(current_user.id, WikiSearchParams(limit=MAX_CANDIDATES), db)
    candidates = [
        {"id": e.id, "title": e.title, "summary": e.summary, "tags": e.tags or [], "content": e.content}
        for e in existing
    ]
    draft = await draft_article(data.selected_text, candidates, allow_merge=data.allow_merge)
    if draft is None:
        raise HTTPException(status_code=502, detail="AI 정리에 실패했습니다. 원문 그대로 저장하거나 잠시 후 다시 시도해 주세요.")
    return draft


@router.post("/", response_model=WikiEntryResponse)
async def create_wiki_entry(
    data: WikiEntryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Create a new wiki entry."""
    entry = await WikiService.create_entry(current_user.id, data, db)
    return _to_response(entry, await WikiService.link_graph(current_user.id, db))


@router.get("/lint", response_model=WikiLintReport)
async def lint_wiki(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """중복·오래된·고아·깨진 연결·요약 없는 문서를 점검한다."""
    return await WikiService.lint(current_user.id, db)


@router.post("/{entry_id}/merge", response_model=WikiEntryResponse)
async def merge_wiki_entry(
    entry_id: str,
    data: WikiMergeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """기존 문서에 새 내용을 합친 결과를 반영한다."""
    entry = await WikiService.merge_entry(current_user.id, entry_id, data, db)
    if not entry:
        raise HTTPException(status_code=404, detail="Wiki entry not found")
    return _to_response(entry, await WikiService.link_graph(current_user.id, db))


@router.get("/{entry_id}", response_model=WikiEntryResponse)
async def get_wiki_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get a specific wiki entry by ID."""
    entry = await WikiService.get_entry(current_user.id, entry_id, db)
    if not entry:
        raise HTTPException(status_code=404, detail="Wiki entry not found")
    return _to_response(entry, await WikiService.link_graph(current_user.id, db))


@router.put("/{entry_id}", response_model=WikiEntryResponse)
async def update_wiki_entry(
    entry_id: str,
    data: WikiEntryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Update an existing wiki entry."""
    entry = await WikiService.update_entry(current_user.id, entry_id, data, db)
    if not entry:
        raise HTTPException(status_code=404, detail="Wiki entry not found")
    return _to_response(entry, await WikiService.link_graph(current_user.id, db))


@router.delete("/{entry_id}")
async def delete_wiki_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Delete a wiki entry."""
    deleted = await WikiService.delete_entry(current_user.id, entry_id, db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Wiki entry not found")
    return {"status": "deleted"}


@router.get("/search/", response_model=List[WikiEntryResponse])
async def search_wiki_entries(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Full-text search in wiki entries."""
    entries = await WikiService.search_entries(current_user.id, q, db, limit)
    return [_to_response(e) for e in entries]

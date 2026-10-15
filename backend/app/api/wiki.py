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
)
from app.services.wiki_service import WikiService

router = APIRouter()


def _to_response(entry) -> WikiEntryResponse:
    """Convert WikiEntry model to response schema."""
    return WikiEntryResponse(
        id=entry.id,
        user_id=entry.user_id,
        title=entry.title,
        content=entry.content,
        category=entry.category,
        tags=entry.tags or [],
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
    return [_to_response(e) for e in entries]


@router.post("/", response_model=WikiEntryResponse)
async def create_wiki_entry(
    data: WikiEntryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Create a new wiki entry."""
    entry = await WikiService.create_entry(current_user.id, data, db)
    return _to_response(entry)


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
    return _to_response(entry)


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
    return _to_response(entry)


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

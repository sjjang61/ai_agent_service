"""Memory management API endpoints."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.memory import (
    MemoryCreate,
    MemoryUpdate,
    MemoryResponse,
    MemorySearchParams,
    ShortTermMemoryResponse,
)
from app.services.memory_service import MemoryService, ShortTermMemoryService
from app.services.schedule_service import aware

router = APIRouter()


def _to_response(memory) -> MemoryResponse:
    """Convert Memory model to response schema."""
    return MemoryResponse(
        id=memory.id,
        category=memory.category,
        memory_type=memory.memory_type or "semantic",
        occurred_at=aware(memory.occurred_at),
        detail=memory.detail or None,
        key=memory.key,
        value=memory.value,
        tags=memory.tags or [],
        source=memory.source,
        importance=memory.importance,
        is_active=memory.is_active,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@router.get("/", response_model=List[MemoryResponse])
async def list_memories(
    query: Optional[str] = Query(None, description="Search keyword"),
    category: Optional[str] = Query(None),
    memory_type: Optional[str] = Query(None, pattern="^(semantic|episodic|procedural)$"),
    min_importance: Optional[int] = Query(None, ge=1, le=10),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """List user's long-term memories with optional filtering."""
    params = MemorySearchParams(
        query=query,
        category=category,
        memory_type=memory_type,
        min_importance=min_importance,
        limit=limit,
        offset=offset,
    )
    memories = await MemoryService.list_memories(current_user.id, params, db)
    return [_to_response(m) for m in memories]


@router.post("/", response_model=MemoryResponse)
async def create_memory(
    data: MemoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Create a new long-term memory."""
    # Check for duplicate key
    existing = await MemoryService.get_by_key(current_user.id, data.key, db)
    if existing:
        raise HTTPException(
            status_code=409, detail=f"Memory with key '{data.key}' already exists"
        )

    memory = await MemoryService.create_memory(current_user.id, data, db)
    return _to_response(memory)


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get a specific memory by ID."""
    memory = await MemoryService.get_memory(current_user.id, memory_id, db)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return _to_response(memory)


@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    data: MemoryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Update an existing memory."""
    memory = await MemoryService.update_memory(current_user.id, memory_id, data, db)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return _to_response(memory)


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Delete a memory."""
    deleted = await MemoryService.delete_memory(current_user.id, memory_id, db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "deleted"}


# Short-term memory endpoints


@router.get("/short/{conversation_id}", response_model=ShortTermMemoryResponse)
async def get_short_term_memories(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get all short-term memories for a conversation."""
    memories = await ShortTermMemoryService.get_all(current_user.id, conversation_id)
    return ShortTermMemoryResponse(
        conversation_id=conversation_id,
        memories=memories,
    )


@router.delete("/short/{conversation_id}")
async def clear_short_term_memories(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
):
    """Clear all short-term memories for a conversation."""
    await ShortTermMemoryService.clear_conversation(current_user.id, conversation_id)
    return {"status": "cleared"}

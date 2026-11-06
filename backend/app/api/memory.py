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
    ShortTermItem,
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
        expires_at=aware(memory.expires_at),
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


# Short-term memory endpoints
# ⚠ GET /short 는 아래 GET /{memory_id} 보다 먼저 선언해야 한다 (뒤에 두면 'short' 가 memory_id 로 해석되어 404 가 난다)
@router.get("/short", response_model=List[ShortTermItem])
async def list_all_short_term_memories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """사용자의 모든 대화방의 단기 메모리 (대화 제목·남은 유지 시간 포함). 대화방 최근 사용 순."""
    from sqlalchemy import select

    from app.models.conversation import Conversation

    items = await ShortTermMemoryService.list_all(current_user.id)
    ids = {i["conversation_id"] for i in items}
    convs = {}
    if ids:
        rows = (await db.execute(select(Conversation.id, Conversation.title, Conversation.updated_at).where(
            Conversation.id.in_(ids), Conversation.user_id == current_user.id))).all()
        convs = {r[0]: (r[1], r[2]) for r in rows}
    items = [i for i in items if i["conversation_id"] in convs]  # 삭제됐거나 남의 대화방 항목은 보이지 않는다
    items.sort(key=lambda i: (convs[i["conversation_id"]][1], i["key"]), reverse=True)
    return [
        ShortTermItem(conversation_id=i["conversation_id"], conversation_title=convs[i["conversation_id"]][0],
                      key=i["key"], value=i["value"], expires_in_seconds=i["ttl"])
        for i in items
    ]


@router.delete("/short/{conversation_id}/{key}")
async def delete_short_term_memory(
    conversation_id: str,
    key: str,
    current_user: User = Depends(get_current_user),
):
    """대화방의 단기 메모리 한 항목을 지운다."""
    await ShortTermMemoryService.delete(current_user.id, conversation_id, key)
    return {"status": "deleted"}


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

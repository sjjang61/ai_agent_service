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
    MergedItem,
    ShortGroup,
    ShortGroupResult,
    ShortMergeApply,
    ShortMergePreview,
    ShortMergeRequest,
    ShortMergeResult,
    ShortRef,
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


async def _short_items(user_id: str, db: AsyncSession) -> List[dict]:
    """GET /short 와 같은 항목 목록(대화 제목 포함)을 dict 로."""
    from sqlalchemy import select

    from app.models.conversation import Conversation

    items = await ShortTermMemoryService.list_all(user_id)
    ids = {i["conversation_id"] for i in items}
    convs = {}
    if ids:
        rows = (await db.execute(select(Conversation.id, Conversation.title, Conversation.updated_at).where(
            Conversation.id.in_(ids), Conversation.user_id == user_id))).all()
        convs = {r[0]: (r[1], r[2]) for r in rows}
    out = []
    for i in items:
        if i["conversation_id"] in convs:
            out.append({**i, "conversation_title": convs[i["conversation_id"]][0], "updated_at": convs[i["conversation_id"]][1]})
    out.sort(key=lambda i: (i["updated_at"], i["key"]), reverse=True)
    return out


@router.post("/short/group", response_model=ShortGroupResult)
async def group_short_term_memories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """모든 대화방의 단기 메모리를 비슷한 내용(주제)끼리 묶는다 (AI). 데이터는 바꾸지 않는다."""
    from app.services import short_memory_merge as sm

    items = await _short_items(current_user.id, db)
    if not items:
        return ShortGroupResult(groups=[])
    try:
        groups = await sm.group_items(items)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"AI 가 묶지 못했습니다: {type(e).__name__}: {str(e)[:150]} (LLM 서버 설정/응답을 확인하세요)")
    shown = items[: sm.MAX_GROUP_ITEMS]
    return ShortGroupResult(groups=[
        ShortGroup(title=g["title"], items=[ShortRef(conversation_id=shown[i]["conversation_id"], key=shown[i]["key"]) for i in g["indices"]])
        for g in groups
    ])


async def _load_group(user_id: str, refs: List[ShortRef], db: AsyncSession):
    """요청한 항목을 Redis 에서 읽어 [{conversation_id, conversation_title, key, value, updated_at}] 로 (내 항목만, 없어진 것은 제외)."""
    by_ref = {(i["conversation_id"], i["key"]): i for i in await _short_items(user_id, db)}
    chosen = [by_ref[(r.conversation_id, r.key)] for r in refs if (r.conversation_id, r.key) in by_ref]
    seen, uniq = set(), []
    for it in chosen:
        k = (it["conversation_id"], it["key"])
        if k not in seen:
            seen.add(k)
            uniq.append(it)
    return uniq


@router.post("/short/merge/preview", response_model=ShortMergePreview)
async def preview_short_term_merge(
    data: ShortMergeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """한 그룹의 항목을 합친 결과를 미리 보여 준다 (저장하지 않는다). 합친 항목은 가장 최근에 쓴 대화방에 저장된다."""
    from app.services import short_memory_merge as sm

    items = await _load_group(current_user.id, data.items, db)
    if len(items) < 2:
        raise HTTPException(status_code=404, detail="합칠 항목을 찾을 수 없습니다 (이미 만료되었거나 삭제되었습니다)")
    try:
        merged = await sm.merge_group(items)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"AI 가 합치지 못했습니다: {type(e).__name__}")
    target = max(items, key=lambda i: i["updated_at"])
    return ShortMergePreview(
        target_conversation_id=target["conversation_id"], target_conversation_title=target["conversation_title"],
        merged=[MergedItem(**m) for m in merged], source_count=len(items),
        conversation_count=len({i["conversation_id"] for i in items}),
    )


@router.post("/short/merge/apply", response_model=ShortMergeResult)
async def apply_short_term_merge(
    data: ShortMergeApply,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """미리보기에서 확인한 합친 항목을 대상 대화방에 저장하고, 합쳐진 원본 항목을 지운다."""
    from app.services.short_memory_merge import unique_key

    items = await _load_group(current_user.id, data.items, db)
    originals = {(i["conversation_id"], i["key"]) for i in items}
    if len(originals) < 2:
        raise HTTPException(status_code=404, detail="합칠 항목을 찾을 수 없습니다 (이미 만료되었거나 삭제되었습니다)")
    if data.target_conversation_id not in {c for c, _ in originals}:
        raise HTTPException(status_code=400, detail="합친 항목은 선택한 항목이 있는 대화방에만 저장할 수 있습니다")
    # 대상 대화방에서 합치는 항목이 아닌 기존 key 와 겹치지 않게 한다
    taken = set(await ShortTermMemoryService.list_keys(current_user.id, data.target_conversation_id)) - {k for c, k in originals if c == data.target_conversation_id}
    saved_keys = set()
    for m in data.merged:
        key = unique_key(m.key, taken | saved_keys)
        saved_keys.add(key)
        await ShortTermMemoryService.store(current_user.id, data.target_conversation_id, key, m.value)
    removed = 0
    for conv, key in originals:
        if conv == data.target_conversation_id and key in saved_keys:
            continue  # 같은 key 로 덮어쓴 항목은 지우지 않는다
        await ShortTermMemoryService.delete(current_user.id, conv, key)
        removed += 1
    return ShortMergeResult(saved=len(saved_keys), removed=removed)


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

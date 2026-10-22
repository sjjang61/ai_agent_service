"""Memory service for long-term (MySQL) and short-term (Redis) memory operations."""
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

import redis.asyncio as aioredis
from sqlalchemy import select, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.memory import Memory
from app.schemas.memory import MemoryCreate, MemoryUpdate, MemorySearchParams, default_type_for

# 에피소드(사례) 기억은 시간이 지날수록 중요도가 반감기만큼씩 줄어든다
EPISODE_HALF_LIFE_DAYS = 90
EPISODE_PRUNE_BELOW = 1.0  # 실효 중요도가 이 값 미만인 자동 추출 사례는 비활성화
MAX_EPISODES_IN_PROMPT = 3
MAX_FACTS_IN_PROMPT = 15
MAX_PROCEDURES_IN_PROMPT = 15


def _utc_naive(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def effective_importance(m: Memory, now: Optional[datetime] = None) -> float:
    """사실·절차는 저장된 중요도 그대로, 에피소드는 나이에 따라 감쇠한 값."""
    base = float(m.importance or 5)
    if m.memory_type != "episodic":
        return base
    when = m.occurred_at or m.created_at
    if when is None:
        return base
    age_days = max(0.0, ((now or _now()) - _utc_naive(when)).total_seconds() / 86400)
    return base * 0.5 ** (age_days / EPISODE_HALF_LIFE_DAYS)


_TOKEN_RE = re.compile(r"[0-9A-Za-z_]{2,}|[가-힣]{2,}")


def tokens(text: str) -> set:
    """검색용 토큰. 한국어는 조사 때문에 어절 단위 일치가 어려워 2~3글자 접두어도 함께 쓴다."""
    out = set()
    for t in _TOKEN_RE.findall((text or "").lower()):
        out.add(t)
        if re.match(r"[가-힣]", t) and len(t) > 2:
            out.add(t[:2])
            out.add(t[:3])
    return out


def episode_text(m: Memory) -> str:
    d = m.detail or {}
    return " ".join([m.key, m.value, d.get("situation", ""), d.get("resolution", ""), d.get("outcome", "")])


def rank_episodes(episodes: List[Memory], query: str, limit: int, now: Optional[datetime] = None) -> List[Memory]:
    """현재 요청과 키워드가 겹치는 사례만 (겹침 수 × 실효 중요도) 순으로 고른다."""
    q = tokens(query)
    scored = []
    for m in episodes:
        hits = len(q & tokens(episode_text(m)))
        if hits:
            scored.append((hits * effective_importance(m, now), m))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:limit]]


class MemoryService:
    """Long-term memory (MySQL) operations."""

    @staticmethod
    async def list_memories(
        user_id: str,
        params: MemorySearchParams,
        db: AsyncSession,
    ) -> List[Memory]:
        """List memories with optional filtering."""
        query = select(Memory).where(
            Memory.user_id == user_id,
            Memory.is_active == True,  # noqa: E712
        )

        if params.category:
            query = query.where(Memory.category == params.category)
        if params.memory_type:
            query = query.where(Memory.memory_type == params.memory_type)
        if params.min_importance:
            query = query.where(Memory.importance >= params.min_importance)
        if params.query:
            pattern = f"%{params.query}%"
            query = query.where(
                or_(
                    Memory.key.ilike(pattern),
                    Memory.value.ilike(pattern),
                )
            )

        query = query.order_by(Memory.importance.desc(), Memory.updated_at.desc())
        query = query.offset(params.offset).limit(params.limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_memory(
        user_id: str, memory_id: str, db: AsyncSession
    ) -> Optional[Memory]:
        """Get a single memory by ID."""
        result = await db.execute(
            select(Memory).where(
                Memory.id == memory_id,
                Memory.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_key(
        user_id: str, key: str, db: AsyncSession
    ) -> Optional[Memory]:
        """Get a memory by key."""
        result = await db.execute(
            select(Memory).where(
                Memory.user_id == user_id,
                Memory.key == key,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_memory(
        user_id: str,
        data: MemoryCreate,
        db: AsyncSession,
        source: str = "manual",
        conversation_id: Optional[str] = None,
    ) -> Memory:
        """Create a new memory."""
        mtype = data.memory_type or default_type_for(data.category)
        memory = Memory(
            user_id=user_id,
            memory_type=mtype,
            occurred_at=(_utc_naive(data.occurred_at) or _now()) if mtype == "episodic" else None,
            detail=data.detail.model_dump() if data.detail and mtype == "episodic" else None,
            category=data.category,
            key=data.key,
            value=data.value,
            tags=data.tags,
            importance=data.importance,
            source=source,
            conversation_id=conversation_id,
        )
        db.add(memory)
        await db.commit()
        await db.refresh(memory)
        return memory

    @staticmethod
    async def update_memory(
        user_id: str,
        memory_id: str,
        data: MemoryUpdate,
        db: AsyncSession,
    ) -> Optional[Memory]:
        """Update an existing memory."""
        memory = await MemoryService.get_memory(user_id, memory_id, db)
        if not memory:
            return None
        for k, v in data.model_dump(exclude_none=True).items():
            setattr(memory, k, v)
        await db.commit()
        await db.refresh(memory)
        return memory

    @staticmethod
    async def delete_memory(
        user_id: str, memory_id: str, db: AsyncSession
    ) -> bool:
        """Delete a memory."""
        result = await db.execute(
            delete(Memory).where(
                Memory.id == memory_id,
                Memory.user_id == user_id,
            )
        )
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def get_context_memories(
        user_id: str,
        db: AsyncSession,
        limit: int = 20,
        categories: Optional[List[str]] = None,
    ) -> List[Memory]:
        """Get top memories for agent context injection."""
        query = select(Memory).where(
            Memory.user_id == user_id,
            Memory.is_active == True,  # noqa: E712
        )
        if categories:
            query = query.where(Memory.category.in_(categories))
        query = query.order_by(Memory.importance.desc()).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_prompt_memories(
        user_id: str, db: AsyncSession, query: str = ""
    ) -> Dict[str, List[Memory]]:
        """시스템 프롬프트에 넣을 장기 메모리를 종류별로 고른다.
        semantic/procedural 은 중요도 상위, episodic 은 현재 요청과 관련된 사례만."""
        rows = (
            await db.execute(
                select(Memory).where(Memory.user_id == user_id, Memory.is_active == True)  # noqa: E712
                .order_by(Memory.importance.desc(), Memory.updated_at.desc())
            )
        ).scalars().all()
        by_type: Dict[str, List[Memory]] = {"semantic": [], "procedural": [], "episodic": []}
        for m in rows:
            by_type.setdefault(m.memory_type or "semantic", by_type["semantic"]).append(m)
        return {
            "semantic": by_type["semantic"][:MAX_FACTS_IN_PROMPT],
            "procedural": by_type["procedural"][:MAX_PROCEDURES_IN_PROMPT],
            "episodic": rank_episodes(by_type["episodic"], query, MAX_EPISODES_IN_PROMPT),
        }

    @staticmethod
    async def prune_stale_episodes(user_id: str, db: AsyncSession) -> int:
        """오래돼 실효 중요도가 바닥난 '자동 저장' 사례를 비활성화한다 (직접 입력한 것은 유지)."""
        rows = (
            await db.execute(
                select(Memory).where(
                    Memory.user_id == user_id,
                    Memory.memory_type == "episodic",
                    Memory.is_active == True,  # noqa: E712
                    Memory.source != "manual",
                )
            )
        ).scalars().all()
        now = _now()
        stale = [m for m in rows if effective_importance(m, now) < EPISODE_PRUNE_BELOW]
        for m in stale:
            m.is_active = False
        if stale:
            await db.commit()
        return len(stale)


class ShortTermMemoryService:
    """Short-term memory (Redis) operations with TTL."""

    DEFAULT_TTL = 86400  # 24 hours

    @staticmethod
    async def _get_redis() -> aioredis.Redis:
        return await aioredis.from_url(settings.REDIS_URL)

    @staticmethod
    def _key(user_id: str, conversation_id: str, key: str) -> str:
        return f"memory:short:{user_id}:{conversation_id}:{key}"

    @staticmethod
    def _index_key(user_id: str, conversation_id: str) -> str:
        return f"memory:short:index:{user_id}:{conversation_id}"

    @staticmethod
    async def store(
        user_id: str,
        conversation_id: str,
        key: str,
        value: str,
        ttl_seconds: int = DEFAULT_TTL,
    ):
        """Store a short-term memory with TTL."""
        redis = await ShortTermMemoryService._get_redis()
        try:
            full_key = ShortTermMemoryService._key(user_id, conversation_id, key)
            index_key = ShortTermMemoryService._index_key(user_id, conversation_id)

            await redis.set(full_key, value, ex=ttl_seconds)
            await redis.sadd(index_key, key)
            await redis.expire(index_key, ttl_seconds)
        finally:
            await redis.close()

    @staticmethod
    async def retrieve(
        user_id: str, conversation_id: str, key: str
    ) -> Optional[str]:
        """Retrieve a short-term memory."""
        redis = await ShortTermMemoryService._get_redis()
        try:
            full_key = ShortTermMemoryService._key(user_id, conversation_id, key)
            value = await redis.get(full_key)
            return value.decode() if value else None
        finally:
            await redis.close()

    @staticmethod
    async def list_keys(user_id: str, conversation_id: str) -> List[str]:
        """List all short-term memory keys for a conversation."""
        redis = await ShortTermMemoryService._get_redis()
        try:
            index_key = ShortTermMemoryService._index_key(user_id, conversation_id)
            keys = await redis.smembers(index_key)
            return [k.decode() for k in keys]
        finally:
            await redis.close()

    @staticmethod
    async def get_all(user_id: str, conversation_id: str) -> dict:
        """Get all short-term memories for a conversation."""
        redis = await ShortTermMemoryService._get_redis()
        try:
            index_key = ShortTermMemoryService._index_key(user_id, conversation_id)
            keys = await redis.smembers(index_key)

            result = {}
            for k in keys:
                key_str = k.decode()
                full_key = ShortTermMemoryService._key(
                    user_id, conversation_id, key_str
                )
                value = await redis.get(full_key)
                if value:
                    result[key_str] = value.decode()

            return result
        finally:
            await redis.close()

    @staticmethod
    async def delete(user_id: str, conversation_id: str, key: str):
        """Delete a short-term memory."""
        redis = await ShortTermMemoryService._get_redis()
        try:
            full_key = ShortTermMemoryService._key(user_id, conversation_id, key)
            index_key = ShortTermMemoryService._index_key(user_id, conversation_id)

            await redis.delete(full_key)
            await redis.srem(index_key, key)
        finally:
            await redis.close()

    @staticmethod
    async def clear_conversation(user_id: str, conversation_id: str):
        """Clear all short-term memories for a conversation."""
        redis = await ShortTermMemoryService._get_redis()
        try:
            index_key = ShortTermMemoryService._index_key(user_id, conversation_id)
            keys = await redis.smembers(index_key)

            for k in keys:
                full_key = ShortTermMemoryService._key(
                    user_id, conversation_id, k.decode()
                )
                await redis.delete(full_key)
            await redis.delete(index_key)
        finally:
            await redis.close()

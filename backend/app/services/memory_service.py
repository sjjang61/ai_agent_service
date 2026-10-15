"""Memory service for long-term (MySQL) and short-term (Redis) memory operations."""
from typing import List, Optional

import redis.asyncio as aioredis
from sqlalchemy import select, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.memory import Memory
from app.schemas.memory import MemoryCreate, MemoryUpdate, MemorySearchParams


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
        memory = Memory(
            user_id=user_id,
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

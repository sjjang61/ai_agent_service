"""Wiki service for CRUD operations."""

from typing import List, Optional

from sqlalchemy import select, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wiki_entry import WikiEntry
from app.schemas.wiki import WikiEntryCreate, WikiEntryUpdate, WikiSearchParams


class WikiService:
    """Wiki entry CRUD operations."""

    @staticmethod
    async def list_entries(
        user_id: str,
        params: WikiSearchParams,
        db: AsyncSession,
    ) -> List[WikiEntry]:
        """List wiki entries with optional filtering."""
        query = select(WikiEntry).where(WikiEntry.user_id == user_id)

        # Category filter
        if params.category:
            query = query.where(WikiEntry.category == params.category)

        # Tags filter (if any tag matches)
        # Note: This is a simple Python-level filter after query
        # For production, consider using JSON operators for better performance

        # Keyword search in title and content
        if params.query:
            pattern = f"%{params.query}%"
            query = query.where(
                or_(
                    WikiEntry.title.ilike(pattern),
                    WikiEntry.content.ilike(pattern),
                )
            )

        # Order by most recent first
        query = query.order_by(WikiEntry.updated_at.desc(), WikiEntry.created_at.desc())
        query = query.offset(params.offset).limit(params.limit)

        result = await db.execute(query)
        entries = list(result.scalars().all())

        # Filter by tags in Python if needed
        if params.tags:
            entries = [
                e for e in entries
                if any(tag in (e.tags or []) for tag in params.tags)
            ]

        return entries

    @staticmethod
    async def get_entry(
        user_id: str, entry_id: str, db: AsyncSession
    ) -> Optional[WikiEntry]:
        """Get a single wiki entry by ID."""
        result = await db.execute(
            select(WikiEntry).where(
                WikiEntry.id == entry_id,
                WikiEntry.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_entry(
        user_id: str,
        data: WikiEntryCreate,
        db: AsyncSession,
    ) -> WikiEntry:
        """Create a new wiki entry."""
        entry = WikiEntry(
            user_id=user_id,
            title=data.title,
            content=data.content,
            category=data.category,
            tags=data.tags,
            source_message_id=data.source_message_id,
            source_conversation_id=data.source_conversation_id,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry

    @staticmethod
    async def update_entry(
        user_id: str,
        entry_id: str,
        data: WikiEntryUpdate,
        db: AsyncSession,
    ) -> Optional[WikiEntry]:
        """Update an existing wiki entry."""
        entry = await WikiService.get_entry(user_id, entry_id, db)
        if not entry:
            return None

        for k, v in data.model_dump(exclude_none=True).items():
            setattr(entry, k, v)

        await db.commit()
        await db.refresh(entry)
        return entry

    @staticmethod
    async def delete_entry(
        user_id: str, entry_id: str, db: AsyncSession
    ) -> bool:
        """Delete a wiki entry."""
        result = await db.execute(
            delete(WikiEntry).where(
                WikiEntry.id == entry_id,
                WikiEntry.user_id == user_id,
            )
        )
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def search_entries(
        user_id: str,
        query_text: str,
        db: AsyncSession,
        limit: int = 20,
    ) -> List[WikiEntry]:
        """Full-text search in wiki entries."""
        pattern = f"%{query_text}%"
        result = await db.execute(
            select(WikiEntry)
            .where(
                WikiEntry.user_id == user_id,
                or_(
                    WikiEntry.title.ilike(pattern),
                    WikiEntry.content.ilike(pattern),
                ),
            )
            .order_by(WikiEntry.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

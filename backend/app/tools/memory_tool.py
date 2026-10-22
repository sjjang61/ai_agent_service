"""Memory tool for Agent to store and retrieve information."""
import json
from typing import Literal, Optional, Callable

from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

from app.services.memory_service import MemoryService, ShortTermMemoryService
from app.schemas.memory import EpisodeDetail, MemoryCreate, MemoryUpdate


class MemoryInput(BaseModel):
    action: Literal[
        "store", "retrieve", "list", "search", "store_short", "retrieve_short"
    ] = Field(
        description=(
            "Action: store (long-term), retrieve (long-term by key), "
            "list (all long-term), search (keyword search), "
            "store_short (conversation scope), retrieve_short"
        )
    )
    key: Optional[str] = Field(default=None, description="Memory key/identifier")
    value: Optional[str] = Field(default=None, description="Value to store")
    category: Optional[str] = Field(
        default="general",
        description="Category: preference, fact, instruction, general",
    )
    query: Optional[str] = Field(
        default=None, description="Search query for keyword matching"
    )
    importance: Optional[int] = Field(
        default=5, description="Importance 1-10 (higher = more likely to be recalled)"
    )
    memory_type: Optional[Literal["semantic", "episodic", "procedural"]] = Field(
        default=None,
        description=(
            "Long-term kind: semantic (stable fact about the user), procedural (how the agent should "
            "act, phrased as an action), episodic (a past event/solved case; also give situation/resolution/outcome). "
            "Omit to infer from category."
        ),
    )
    situation: Optional[str] = Field(default=None, description="episodic: the situation or problem")
    resolution: Optional[str] = Field(default=None, description="episodic: how it was resolved")
    outcome: Optional[str] = Field(default=None, description="episodic: the result")


class MemoryTool(BaseTool):
    """Tool for storing and retrieving information across conversations."""

    name: str = "memory_tool"
    description: str = (
        "Store and retrieve information across conversations. "
        "Use store/retrieve for long-term facts (user preferences, important info). "
        "Use store_short/retrieve_short for current task context within this conversation. "
        "Use search to find memories by keyword. "
        "Long-term memory has three kinds (memory_type): semantic = stable facts about the user; "
        "procedural = how to act, written as an action (e.g. 'show example code first, then explain'); "
        "episodic = a specific past event or solved case (provide situation, resolution, outcome). "
        "Categories: preference, fact, instruction, general."
    )
    args_schema: type[BaseModel] = MemoryInput
    user_id: str = ""
    conversation_id: str = ""
    db_session_factory: Optional[Callable] = None

    async def _arun(
        self,
        action: str,
        key: str = None,
        value: str = None,
        category: str = "general",
        query: str = None,
        importance: int = 5,
        memory_type: str = None,
        situation: str = None,
        resolution: str = None,
        outcome: str = None,
    ) -> str:
        try:
            if action == "store":
                return await self._store_long_term(
                    key, value, category, importance, memory_type, situation, resolution, outcome
                )
            elif action == "retrieve":
                return await self._retrieve_long_term(key)
            elif action == "list":
                return await self._list_long_term()
            elif action == "search":
                return await self._search_long_term(query)
            elif action == "store_short":
                return await self._store_short_term(key, value)
            elif action == "retrieve_short":
                return await self._retrieve_short_term(key)
            return f"Unknown action: {action}"
        except Exception as e:
            return f"Memory error: {type(e).__name__}: {e}"

    def _run(
        self,
        action: str,
        key: str = None,
        value: str = None,
        category: str = "general",
        query: str = None,
        importance: int = 5,
        memory_type: str = None,
        situation: str = None,
        resolution: str = None,
        outcome: str = None,
    ) -> str:
        import asyncio

        return asyncio.get_event_loop().run_until_complete(
            self._arun(action, key, value, category, query, importance, memory_type, situation, resolution, outcome)
        )

    async def _store_long_term(
        self, key: str, value: str, category: str, importance: int,
        memory_type: str = None, situation: str = None, resolution: str = None, outcome: str = None,
    ) -> str:
        if not key or not value:
            return "Error: key and value are required for store"

        if not self.db_session_factory:
            return "Error: Database session not available"

        detail = None
        if memory_type == "episodic":
            if not situation or not resolution:
                return "Error: episodic memory requires situation and resolution"
            detail = EpisodeDetail(situation=situation, resolution=resolution, outcome=outcome or "")

        async with self.db_session_factory() as db:
            existing = await MemoryService.get_by_key(self.user_id, key, db)
            if existing:
                # Update existing
                await MemoryService.update_memory(
                    self.user_id,
                    existing.id,
                    MemoryUpdate(
                        value=value, category=category, importance=importance,
                        memory_type=memory_type, detail=detail,
                    ),
                    db,
                )
                return f"Updated memory: {key}"
            else:
                # Create new
                await MemoryService.create_memory(
                    self.user_id,
                    MemoryCreate(
                        key=key,
                        value=value,
                        category=category,
                        importance=importance,
                        memory_type=memory_type,
                        detail=detail,
                    ),
                    db,
                    source="agent",
                    conversation_id=self.conversation_id,
                )
                return f"Stored memory: {key}"

    async def _retrieve_long_term(self, key: str) -> str:
        if not key:
            return "Error: key is required for retrieve"

        if not self.db_session_factory:
            return "Error: Database session not available"

        async with self.db_session_factory() as db:
            memory = await MemoryService.get_by_key(self.user_id, key, db)
            if memory:
                return f"{memory.key}: {memory.value}"
            return f"No memory found for key: {key}"

    async def _list_long_term(self) -> str:
        if not self.db_session_factory:
            return "Error: Database session not available"

        from app.schemas.memory import MemorySearchParams

        async with self.db_session_factory() as db:
            memories = await MemoryService.list_memories(
                self.user_id, MemorySearchParams(limit=20), db
            )
            if not memories:
                return "No memories stored"
            return json.dumps(
                [
                    {
                        "key": m.key,
                        "category": m.category,
                        "memory_type": m.memory_type,
                        "importance": m.importance,
                    }
                    for m in memories
                ],
                ensure_ascii=False,
            )

    async def _search_long_term(self, query: str) -> str:
        if not query:
            return "Error: query is required for search"

        if not self.db_session_factory:
            return "Error: Database session not available"

        from app.schemas.memory import MemorySearchParams

        async with self.db_session_factory() as db:
            memories = await MemoryService.list_memories(
                self.user_id, MemorySearchParams(query=query, limit=10), db
            )
            if not memories:
                return f"No memories found matching: {query}"
            return json.dumps(
                [
                    {
                        "key": m.key,
                        "value": m.value[:200],
                        "category": m.category,
                        "memory_type": m.memory_type,
                    }
                    for m in memories
                ],
                ensure_ascii=False,
            )

    async def _store_short_term(self, key: str, value: str) -> str:
        if not key or not value:
            return "Error: key and value are required"
        await ShortTermMemoryService.store(
            self.user_id, self.conversation_id, key, value
        )
        return f"Stored short-term: {key}"

    async def _retrieve_short_term(self, key: str) -> str:
        if not key:
            return "Error: key is required"
        value = await ShortTermMemoryService.retrieve(
            self.user_id, self.conversation_id, key
        )
        return value if value else f"No short-term memory for: {key}"

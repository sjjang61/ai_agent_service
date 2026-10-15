"""Automatic memory extraction from agent conversations."""
import json
import logging
import re
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.schemas.memory import MemoryCreate
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Analyze this conversation and extract any important user information that should be remembered for future conversations.

User message: {user_message}
Agent response: {agent_response}

Extract information in these categories:
- preference: User preferences (language, style, tools they like)
- fact: Facts about the user (job, skills, projects, name)
- instruction: Standing instructions (always do X, never do Y)

Return ONLY a JSON array of memories to store (no other text):
[{{"key": "unique_key", "value": "what to remember", "category": "preference|fact|instruction", "importance": 1-10}}]

Rules:
- Return empty array [] if nothing worth remembering
- Only extract truly important, reusable information
- Skip transient task details (current file being edited, temporary data)
- Use snake_case for keys (e.g., "preferred_language", "coding_style")
- Keep values concise but informative
- importance: 1-3 (low), 4-6 (medium), 7-10 (high/critical)
"""


class MemoryExtractor:
    """Extract and store important information from conversations."""

    @staticmethod
    async def extract_and_store(
        user_id: str,
        conversation_id: str,
        user_message: str,
        agent_response: str,
        db: AsyncSession,
    ) -> List[str]:
        """
        Analyze conversation and auto-extract memories.
        Returns list of stored memory keys.
        """
        # Skip if extraction is disabled
        if not getattr(settings, "ENABLE_MEMORY_EXTRACTION", True):
            return []

        # Skip very short messages
        if len(user_message) < 20 and len(agent_response) < 100:
            return []

        try:
            extracted = await MemoryExtractor._call_extraction_llm(
                user_message, agent_response
            )
            if not extracted:
                return []

            stored_keys = []
            for item in extracted:
                key = item.get("key")
                value = item.get("value")
                category = item.get("category", "general")
                importance = item.get("importance", 5)

                if not key or not value:
                    continue

                # Validate category
                if category not in ("preference", "fact", "instruction", "general"):
                    category = "general"

                # Validate importance
                if not isinstance(importance, int) or importance < 1:
                    importance = 5
                elif importance > 10:
                    importance = 10

                # Check if already exists
                existing = await MemoryService.get_by_key(user_id, key, db)
                if existing:
                    # Update if value is different
                    if existing.value != value:
                        from app.schemas.memory import MemoryUpdate

                        await MemoryService.update_memory(
                            user_id,
                            existing.id,
                            MemoryUpdate(value=value, importance=importance),
                            db,
                        )
                        stored_keys.append(f"updated:{key}")
                        logger.debug(f"[memory] Updated: {key}")
                else:
                    await MemoryService.create_memory(
                        user_id,
                        MemoryCreate(
                            key=key,
                            value=value,
                            category=category,
                            importance=importance,
                        ),
                        db,
                        source="auto_extracted",
                        conversation_id=conversation_id,
                    )
                    stored_keys.append(key)
                    logger.debug(f"[memory] Created: {key}")

            if stored_keys:
                logger.info(f"[memory] Extracted {len(stored_keys)} memories for user {user_id[:8]}")

            return stored_keys

        except Exception as e:
            logger.warning(f"[memory] Extraction failed: {e}")
            return []

    @staticmethod
    async def _call_extraction_llm(user_message: str, agent_response: str) -> list:
        """Call LLM to extract memories. Returns parsed JSON list."""
        from app.agent.agno_engine import build_agno_model

        prompt = EXTRACTION_PROMPT.format(
            user_message=user_message[:1500],
            agent_response=agent_response[:3000],
        )

        try:
            model = build_agno_model(settings.LLM_TYPE)
            response = await model.ainvoke([{"role": "user", "content": prompt}])
            content = response.content if hasattr(response, "content") else str(response)

            # Parse JSON from response
            # Try to extract JSON array from response
            match = re.search(r"\[.*\]", content, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group())
                    if isinstance(result, list):
                        return result
                except json.JSONDecodeError:
                    pass
            return []
        except Exception as e:
            logger.debug(f"[memory] Extraction LLM call failed: {e}")
            return []


async def maybe_extract_memories(
    user_id: str,
    conversation_id: str,
    user_message: str,
    agent_response: str,
    db: AsyncSession,
) -> None:
    """
    Convenience function to extract memories if enabled.
    Call this after agent response is complete.
    """
    if not getattr(settings, "ENABLE_MEMORY_EXTRACTION", True):
        return

    try:
        await MemoryExtractor.extract_and_store(
            user_id=user_id,
            conversation_id=conversation_id,
            user_message=user_message,
            agent_response=agent_response,
            db=db,
        )
    except Exception as e:
        logger.warning(f"[memory] maybe_extract_memories failed: {e}")

"""대화에서 기억할 만한 사용자 정보를 추출해 단기/장기 메모리에 자동 저장한다."""
import asyncio
import json
import logging
import re
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import render
from app.config import settings
from app.schemas.memory import MemoryCreate, MemoryUpdate
from app.services.memory_service import MemoryService, ShortTermMemoryService

logger = logging.getLogger(__name__)

EXTRACTION_TIMEOUT_SECONDS = 30
MAX_ITEMS_PER_TURN = 5
MIN_USER_MESSAGE_CHARS = 8
MEMORY_TYPES = ("semantic", "procedural", "episodic", "short")

# 값에 이런 패턴이 있으면 비밀 정보로 보고 저장하지 않는다
_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bap]-[A-Za-z0-9-]{10,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|password\s*[:=]|passwd\s*[:=]|비밀번호\s*[:=은는이가]|\b\d{6}-\d{7}\b)",
    re.IGNORECASE,
)
_KEY_RE = re.compile(r"[^a-z0-9_]+")


def _content_text(content) -> str:
    """LangChain 응답 content (str 또는 블록 리스트)를 문자열로."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return str(content)


def parse_items(text: str) -> list:
    """LLM 응답에서 JSON 배열을 꺼내 검증한 항목 목록으로 돌려준다."""
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return []
    try:
        raw = json.loads(m.group())
    except json.JSONDecodeError:
        return []
    items = []
    for it in raw if isinstance(raw, list) else []:
        if not isinstance(it, dict):
            continue
        key = _KEY_RE.sub("_", str(it.get("key", "")).strip().lower()).strip("_")[:100]
        value = str(it.get("value", "")).strip()[:500]
        if not key or not value or _SECRET_RE.search(value):
            continue
        mtype = str(it.get("type") or it.get("scope") or "semantic")
        if mtype == "long":  # 이전 형식과의 호환
            mtype = "procedural" if it.get("category") == "instruction" else "semantic"
        if mtype not in MEMORY_TYPES:
            mtype = "semantic"
        category = it.get("category") if it.get("category") in ("preference", "fact", "instruction") else "general"
        if mtype == "procedural":
            category = "instruction"
        try:
            importance = min(10, max(1, int(it.get("importance", 5))))
        except (TypeError, ValueError):
            importance = 5
        item = {"key": key, "value": value, "type": mtype, "category": category, "importance": importance}
        if mtype == "episodic":
            detail = {k: str(it.get(k) or "").strip()[:500] for k in ("situation", "resolution", "outcome")}
            if not detail["situation"] or not detail["resolution"] or _SECRET_RE.search(" ".join(detail.values())):
                continue  # 상황과 해결이 없는 사례는 쓸모가 없다
            item["detail"] = detail
            item["category"] = "general"
        items.append(item)
        if len(items) >= MAX_ITEMS_PER_TURN:
            break
    return items


class MemoryExtractor:
    @staticmethod
    async def extract_and_store(
        user_id: str,
        conversation_id: str,
        user_message: str,
        agent_response: str,
        db: AsyncSession,
    ) -> List[dict]:
        """대화를 분석해 새로 저장/갱신된 항목 목록을 돌려준다.
        항목: {key, value, memory_type: semantic|procedural|episodic|short, action: added|updated}"""
        if not getattr(settings, "ENABLE_MEMORY_EXTRACTION", True):
            return []
        if len(user_message.strip()) < MIN_USER_MESSAGE_CHARS:
            return []

        try:
            existing = await MemoryService.get_context_memories(user_id, db, limit=30)
            items = await MemoryExtractor._call_extraction_llm(user_message, agent_response, existing)
        except Exception as e:
            logger.warning("[memory] 추출 실패: %s", e)
            return []

        saved: List[dict] = []
        for it in items:
            try:
                action = await MemoryExtractor._store(user_id, conversation_id, it, db)
            except Exception as e:
                logger.warning("[memory] 저장 실패 (%s): %s", it["key"], e)
                continue
            if action:
                saved.append({"key": it["key"], "value": it["value"], "memory_type": it["type"], "action": action})
        try:
            await MemoryService.prune_stale_episodes(user_id, db)
        except Exception as e:
            logger.warning("[memory] 오래된 사례 정리 실패: %s", e)
        if saved:
            logger.info("[memory] 사용자 %s: %d건 저장 (%s)", user_id[:8], len(saved), ", ".join(f"{s['memory_type']}:{s['key']}" for s in saved))
        return saved

    @staticmethod
    async def _store(user_id: str, conversation_id: str, it: dict, db: AsyncSession):
        """저장하면 'added'/'updated', 변화가 없거나 건너뛰면 None."""
        if it["type"] == "short":
            prev = await ShortTermMemoryService.retrieve(user_id, conversation_id, it["key"])
            if prev == it["value"]:
                return None
            await ShortTermMemoryService.store(user_id, conversation_id, it["key"], it["value"])
            return "updated" if prev else "added"

        key = it["key"]
        existing = await MemoryService.get_by_key(user_id, key, db)
        if existing and existing.memory_type != it["type"]:
            # 같은 key 가 다른 종류로 이미 있으면 덮어쓰지 않고 종류를 붙여 따로 저장한다
            key = f"{key}_{it['type']}"
            existing = await MemoryService.get_by_key(user_id, key, db)
        if existing:
            if existing.source == "manual" or (existing.value == it["value"] and not it.get("detail")):
                return None  # 사용자가 직접 입력한 메모리는 자동으로 덮어쓰지 않는다
            await MemoryService.update_memory(
                user_id,
                existing.id,
                MemoryUpdate(value=it["value"], importance=it["importance"], detail=it.get("detail")),
                db,
            )
            return "updated"
        await MemoryService.create_memory(
            user_id,
            MemoryCreate(
                key=key,
                value=it["value"],
                category=it["category"],
                importance=it["importance"],
                memory_type=it["type"],
                detail=it.get("detail"),
            ),
            db,
            source="auto_extracted",
            conversation_id=conversation_id,
        )
        return "added"

    @staticmethod
    async def _call_extraction_llm(user_message: str, agent_response: str, existing: list) -> list:
        # Agno 모델에는 ainvoke 가 없어 LangChain 모델(설정된 LLM_TYPE)을 사용한다
        from app.agent.react_agent import AgentRunner

        llm = AgentRunner(tools=[]).llm
        prompt = render(
            "memory_extraction",
            user_message=user_message[:1500],
            agent_response=agent_response[:1500],
            existing="\n".join(f"- [{m.memory_type}] {m.key}: {m.value}" for m in existing) or "(없음)",
            max_items=MAX_ITEMS_PER_TURN,
        )
        resp = await asyncio.wait_for(llm.ainvoke(prompt), EXTRACTION_TIMEOUT_SECONDS)
        return parse_items(_content_text(resp.content))


async def maybe_extract_memories(
    user_id: str,
    conversation_id: str,
    user_message: str,
    agent_response: str,
    db: AsyncSession,
) -> List[dict]:
    """추출이 켜져 있으면 실행하고, 저장된 항목 목록을 돌려준다 (실패해도 예외를 던지지 않는다)."""
    try:
        return await MemoryExtractor.extract_and_store(user_id, conversation_id, user_message, agent_response, db)
    except Exception as e:
        logger.warning("[memory] maybe_extract_memories 실패: %s", e)
        return []

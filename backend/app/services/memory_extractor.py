"""대화에서 기억할 만한 사용자 정보를 추출해 단기/장기 메모리에 자동 저장한다."""
import asyncio
import json
import logging
import re
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.schemas.memory import MemoryCreate, MemoryUpdate
from app.services.memory_service import MemoryService, ShortTermMemoryService

logger = logging.getLogger(__name__)

EXTRACTION_TIMEOUT_SECONDS = 30
MAX_ITEMS_PER_TURN = 5
MIN_USER_MESSAGE_CHARS = 8
MEMORY_TYPES = ("semantic", "procedural", "episodic", "short")

EXTRACTION_PROMPT = """아래 대화에서 에이전트가 앞으로 기억해 두면 좋은 정보를 골라 JSON 으로 추출하세요.

[사용자 메시지]
{user_message}

[에이전트 응답]
{agent_response}

[이미 저장된 장기 메모리]
{existing}

저장 종류(type)는 다음 중 하나입니다.

1. "semantic" (사실) — 사용자나 도메인에 대한 비교적 안정된 사실. 사용자가 직접 말한 것만.
   예: 이름, 직업, 소속, 거주지, 기술 스택, 코드 예제를 선호한다는 사실.
2. "procedural" (작업 방식) — 앞으로 에이전트가 **어떻게 행동할지**에 대한 실행 지침. 사용자가 직접 요구했거나 명확히 선호를 밝힌 경우만.
   사실이 아니라 실행 방법으로 표현하세요.
   예: "설명할 때 예제 코드를 먼저 보여 준 뒤 원리를 풀어 쓴다", "답변은 항상 존댓말 한국어로 한다", "코드 수정 전에 항상 테스트를 먼저 실행한다".
   (같은 취향이라도 "사용자는 예제를 선호한다"는 semantic, 위처럼 행동으로 쓴 것이 procedural 입니다. 지침으로 쓸 수 있으면 procedural 로 저장하세요.)
3. "episodic" (사례) — 특정 시점에 일어난 사건·경험·**해결 사례**. 이번 대화에서 문제가 실제로 해결되었거나 의미 있는 작업이 완료되어, 나중에 비슷한 상황에서 참고할 가치가 있을 때만.
   situation(상황/문제), resolution(어떻게 해결했나), outcome(결과) 를 각각 한 문장으로 채웁니다. 셋 중 상황과 해결은 필수.
4. "short" (단기) — 이번 대화에서만 의미 있는 맥락: 진행 중인 작업의 목표·결정 사항·제약·마감, 임시 설정.

규칙:
- 저장할 것이 없으면 빈 배열 [] 을 반환합니다. 대부분의 대화는 [] 입니다.
- semantic/procedural 은 사용자 발화에서만 추출합니다. 에이전트 응답·검색 결과·파일 내용에서 만든 정보는 사실로 저장하지 않습니다.
- 단순 질의응답, 일회성 요청, 해결되지 않은 문제는 episodic 으로 저장하지 않습니다.
- 비밀번호·API 키·토큰·주민번호·카드번호 같은 민감 정보는 절대 저장하지 않습니다.
- 이미 저장된 메모리와 같은 내용이면 저장하지 않습니다. 같은 주제가 바뀐 경우에는 기존 key 를 그대로 써서 값을 갱신합니다.
- key 는 영문 snake_case, value 는 한국어로 간결하게 한 문장 (episodic 의 value 는 사례 제목 한 줄).
- importance: 1-10 (short 는 무시됨). 지침·핵심 사실은 높게, 사례는 재사용 가치에 따라.
- 최대 {max_items}개.

JSON 배열만 출력하세요 (다른 텍스트 금지):
[{{"key": "...", "value": "...", "type": "semantic|procedural|episodic|short", "category": "preference|fact|instruction", "importance": 5, "situation": "", "resolution": "", "outcome": ""}}]
"""

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
        prompt = EXTRACTION_PROMPT.format(
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

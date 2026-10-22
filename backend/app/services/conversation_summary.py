"""대화 롤링 요약: 컨텍스트 창(최근 HISTORY_WINDOW 개)에서 밀려난 오래된 메시지를 요약해 둔다.

- 에이전트는 최근 메시지만 원문으로 받으므로, 긴 대화에서는 앞부분의 결정·제약이 사라진다.
- 밀려난 메시지가 일정량 쌓이면 이전 요약 + 새로 밀려난 메시지를 LLM 으로 합쳐 새 요약을 만든다.
- 요약은 시스템 프롬프트에 '이 대화의 앞부분 요약' 으로 붙는다.
"""
import asyncio
import logging
from typing import List, Optional

from sqlalchemy import select

from app.agent.memory import HISTORY_WINDOW
from app.agent.prompts import render
from app.config import settings
from app.db.session import AsyncSessionLocal
from app.models.conversation import Conversation
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)

SUMMARY_BATCH = 4  # 밀려난 메시지가 이만큼 쌓일 때마다 요약을 갱신 (LLM 호출 빈도 조절)
SUMMARY_MAX_CHARS = 2500
MESSAGE_CLIP_CHARS = 1500
SUMMARY_TIMEOUT_SECONDS = 60

_running: set = set()  # 같은 대화의 요약이 동시에 돌지 않도록


def _transcript(messages: list) -> str:
    lines = []
    for m in messages:
        if m.role not in ("user", "assistant") or m.content == "__error__":
            continue
        who = "사용자" if m.role == "user" else "에이전트"
        text = (m.content or "").strip()
        if len(text) > MESSAGE_CLIP_CHARS:
            text = text[:MESSAGE_CLIP_CHARS] + " …(생략)"
        lines.append(f"{who}: {text}")
    return "\n\n".join(lines)


def pending_messages(all_messages: list, summary_count: int, window: int = HISTORY_WINDOW) -> list:
    """창 밖으로 밀려났지만 아직 요약에 반영되지 않은 메시지."""
    older = max(0, len(all_messages) - window)
    return all_messages[min(summary_count, older):older]


def summary_context(summary: Optional[str], total_messages: int, window: int = HISTORY_WINDOW) -> str:
    """시스템 프롬프트에 붙일 섹션. 창 안에 모두 들어오는 짧은 대화에는 붙이지 않는다."""
    if not summary or total_messages <= window:
        return ""
    return "\n\n" + render("summary_context", summary=summary.strip()) + "\n\n"


async def _summarize(previous: str, new_messages: list) -> str:
    from app.agent.react_agent import AgentRunner
    from app.services.memory_extractor import _content_text

    llm = AgentRunner(tools=[]).llm
    prompt = render(
        "summary_request",
        max_chars=SUMMARY_MAX_CHARS,
        previous=previous.strip() or "(없음)",
        transcript=_transcript(new_messages) or "(없음)",
    )
    resp = await asyncio.wait_for(llm.ainvoke(prompt), SUMMARY_TIMEOUT_SECONDS)
    return _content_text(resp.content).strip()[: SUMMARY_MAX_CHARS + 500]


async def maybe_update_summary(conversation_id: str) -> bool:
    """밀려난 미요약 메시지가 SUMMARY_BATCH 이상이면 요약을 갱신한다. 갱신했으면 True. 예외는 던지지 않는다."""
    if not getattr(settings, "ENABLE_CONVERSATION_SUMMARY", True) or conversation_id in _running:
        return False
    _running.add(conversation_id)
    try:
        async with AsyncSessionLocal() as db:
            conv = (await db.execute(select(Conversation).where(Conversation.id == conversation_id))).scalar_one_or_none()
            if not conv:
                return False
            messages: List = await ChatService.get_messages(conversation_id, db)
            fresh = pending_messages(messages, conv.summary_count or 0)
            if len(fresh) < SUMMARY_BATCH:
                return False
            summary = await _summarize(conv.summary or "", fresh)
            if not summary:
                return False
            conv.summary = summary
            conv.summary_count = (conv.summary_count or 0) + len(fresh)
            await db.commit()
            logger.info("[summary] 대화 %s 요약 갱신: +%d개 메시지 (누적 %d, %d자)", conversation_id[:8], len(fresh), conv.summary_count, len(summary))
            return True
    except Exception as e:
        logger.warning("[summary] 요약 실패 (%s): %s", conversation_id[:8], e)
        return False
    finally:
        _running.discard(conversation_id)

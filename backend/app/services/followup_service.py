"""답변 뒤에 이어서 물어볼 만한 질문 2개를 만든다. 프롬프트는 prompts/followup_questions.md."""
import asyncio
import json
import logging
import re

from app.agent.prompts import render

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 30
MAX_QUESTIONS = 2
_QUESTION_CLIP = 1500
_ANSWER_CLIP = 3000


def parse_questions(text: str) -> list[str]:
    """LLM 응답(JSON)에서 질문 목록을 꺼내 정리한다. 중복·빈 값·너무 긴 문장은 버리고 최대 MAX_QUESTIONS 개."""
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group())
    except json.JSONDecodeError:
        return []
    raw = data.get("questions") if isinstance(data, dict) else None
    out: list[str] = []
    for q in raw if isinstance(raw, list) else []:
        q = " ".join(str(q).split()).strip("\"'")
        if q and len(q) <= 120 and q not in out:
            out.append(q)
    return out[:MAX_QUESTIONS]


async def suggest_followups(question: str, answer: str) -> list[str]:
    """실패하면 빈 목록 (추천은 부가 기능이라 응답에 영향을 주지 않는다)."""
    try:
        from app.agent.react_agent import AgentRunner
        from app.services.memory_extractor import _content_text

        llm = AgentRunner(tools=[]).llm
        prompt = render("followup_questions", question=question[:_QUESTION_CLIP], answer=answer[:_ANSWER_CLIP])
        resp = await asyncio.wait_for(llm.ainvoke(prompt), TIMEOUT_SECONDS)
        return parse_questions(_content_text(resp.content))
    except Exception as e:  # noqa: BLE001
        logger.warning("[followup] 추천 질문 생성 실패: %s", e)
        return []


_pending: set = set()  # 끝나기 전에 수거되지 않도록 참조를 잡아 둔다


async def attach_suggestions(message_id: str, question: str, answer: str) -> list[str]:
    """추천 질문을 만들어 메시지의 메타데이터(suggestions)에 저장한다. 응답 스트림이 없는 경우(예약 실행 등)에 쓴다:
    사용자가 나중에 그 대화를 열면 일반 채팅 답변처럼 마지막 답변 아래에 추천 질문 2개가 보인다. 실패해도 조용히 넘어간다."""
    items = await suggest_followups(question, answer)
    if not items:
        return []
    try:
        from app.db.session import AsyncSessionLocal
        from app.models.message import Message

        async with AsyncSessionLocal() as db:
            msg = await db.get(Message, message_id)
            if msg is None:
                return []
            msg.metadata_ = {**(msg.metadata_ or {}), "suggestions": items}
            await db.commit()
        return items
    except Exception as e:  # noqa: BLE001
        logger.warning("[followup] 추천 질문 저장 실패: %s", e)
        return []


def schedule_attach(message_id: str, question: str, answer: str) -> "asyncio.Task":
    """attach_suggestions 를 백그라운드로 실행한다 (실행 결과 저장과 알림을 기다리게 하지 않는다)."""
    task = asyncio.create_task(attach_suggestions(message_id, question, answer))
    _pending.add(task)
    task.add_done_callback(_pending.discard)
    return task

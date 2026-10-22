"""턴 의도 판별: 사용자의 마지막 메시지가 '요청'인지 '요청 없는 서술'인지 가른다.

"나는 테니스를 좋아해" 같은 서술에 모델이 직전 요청(주가 조회 등)을 다시 수행하는 문제를 구조적으로 막기 위해,
이전 대화가 있을 때 짧은 메시지는 먼저 가볍게 분류한다. 서술이면 도구·팀 없이 짧은 반응만 하고 끝낸다.
판별이 불확실하거나 실패하면 항상 '요청'으로 보고 평소처럼 처리한다(fail-open).
"""
import asyncio
import json
import logging
import re
from typing import List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

logger = logging.getLogger(__name__)

GATE_MAX_CHARS = 300  # 이보다 긴 메시지(첨부 포함 등)는 거의 항상 요청이므로 판별을 건너뛴다
GATE_TIMEOUT_SECONDS = 20
CONTEXT_MESSAGES = 4
CONTEXT_CLIP = 300

INTENT_PROMPT = """당신은 대화에서 사용자의 마지막 메시지가 에이전트에게 무언가를 요구하는지 분류합니다.

[직전 대화]
{context}

[사용자의 마지막 메시지]
{message}

분류:
- "request": 질문, 지시, 부탁, 정보·작업 요청이거나, 직전 에이전트의 질문·제안에 대한 답/승인("응", "그걸로 해줘", "진행해", "계속해"), 이전 주제를 이어가거나 바꾸는 후속 질문("그럼 ~는?"), 명시적 재요청("다시 해줘")인 경우.
- "statement": 질문도 요청도 없이 자신의 선호·사실·상태·감상을 알려 주거나, 인사·감사·맞장구만 하는 경우. (예: "나는 테니스를 좋아해", "주말엔 등산해", "고마워", "ㅋㅋ 재밌네")

조금이라도 요청일 가능성이 있으면 반드시 "request" 로 분류하세요.
"statement" 이면 reply 에 사용자에게 건넬 자연스러운 한국어 반응을 한두 문장으로 쓰세요. 새로운 정보·조회 결과·제안을 덧붙이거나 이전 대화 내용을 반복하지 마세요.

JSON 만 출력하세요 (다른 텍스트 금지):
{{"intent": "request" | "statement", "reply": "statement 일 때만"}}
"""


def _clip(text: str) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= CONTEXT_CLIP else text[:CONTEXT_CLIP] + "…"


def _context(history: List[BaseMessage]) -> str:
    lines = []
    for m in history[-CONTEXT_MESSAGES:]:
        if isinstance(m, (HumanMessage, AIMessage)) and isinstance(m.content, str):
            lines.append(f"{'사용자' if isinstance(m, HumanMessage) else '에이전트'}: {_clip(m.content)}")
    return "\n".join(lines) or "(없음)"


def parse_intent(text: str) -> Optional[str]:
    """LLM 응답에서 statement 의 reply 를 꺼낸다. statement 가 아니거나 형식이 틀리면 None (=요청으로 처리)."""
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group())
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("intent") != "statement":
        return None
    reply = str(data.get("reply") or "").strip()
    return reply[:400] if reply else None


def prior_history(history: List[BaseMessage], user_input: str) -> List[BaseMessage]:
    """이번 사용자 메시지는 이미 DB(=history)에 저장돼 있으므로 마지막에 있으면 떼어 '이전 대화'만 남긴다."""
    if history and isinstance(history[-1], HumanMessage) and history[-1].content == user_input:
        return history[:-1]
    return history


def should_gate(user_input: str, history: List[BaseMessage], headless: bool) -> bool:
    return bool(history) and not headless and 0 < len(user_input.strip()) <= GATE_MAX_CHARS


async def statement_reply(user_input: str, history: List[BaseMessage]) -> Optional[str]:
    """요청 없는 서술이면 짧은 반응 문장을, 아니면(또는 실패하면) None 을 돌려준다."""
    try:
        from app.agent.react_agent import AgentRunner
        from app.services.memory_extractor import _content_text

        llm = AgentRunner(tools=[]).llm
        prompt = INTENT_PROMPT.format(context=_context(history), message=_clip(user_input))
        resp = await asyncio.wait_for(llm.ainvoke(prompt), GATE_TIMEOUT_SECONDS)
        return parse_intent(_content_text(resp.content))
    except Exception as e:
        logger.warning("[intent] 판별 실패 — 요청으로 처리: %s", e)
        return None

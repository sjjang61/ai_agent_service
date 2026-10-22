"""요청 라우팅: 응답을 만들기 전에 사용자의 마지막 메시지를 세 갈래로 가른다.

- statement: 질문·요청 없는 서술("나는 테니스를 좋아해"). 도구·팀 없이 짧은 반응만 하고 끝낸다.
  (이전 요청을 모델이 다시 수행하는 문제를 구조적으로 막는다)
- simple: 계획이 필요 없는 요청. 지금처럼 바로 에이전트가 처리한다 (a안).
- complex: 여러 단계가 필요한 작업. 같은 호출에서 전체 작업 계획을 만들어 todo 에 넣고 실행한다 (b안).
판별이 불확실하거나 실패하면 항상 simple 로 본다(fail-open).
"""
import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.agent.prompts import render

logger = logging.getLogger(__name__)

STATEMENT_MAX_CHARS = 300  # statement 는 짧은 메시지에서만 인정한다 (긴 메시지는 거의 항상 요청)
MESSAGE_CLIP = 1500
ROUTE_TIMEOUT_SECONDS = 30
CONTEXT_MESSAGES = 4
CONTEXT_CLIP = 300
MIN_PLAN_STEPS = 2
MAX_PLAN_STEPS = 8
PLAN_STEP_CLIP = 80


@dataclass
class Route:
    kind: str = "simple"  # statement | simple | complex
    reply: str = ""  # statement 일 때 사용자에게 건넬 반응
    plan: List[str] = field(default_factory=list)  # complex 일 때 단계 목록


def _clip(text: str, n: int = CONTEXT_CLIP) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n] + "…"


def _context(history: List[BaseMessage]) -> str:
    lines = []
    for m in history[-CONTEXT_MESSAGES:]:
        if isinstance(m, (HumanMessage, AIMessage)) and isinstance(m.content, str):
            lines.append(f"{'사용자' if isinstance(m, HumanMessage) else '에이전트'}: {_clip(m.content)}")
    return "\n".join(lines) or "(없음)"


def parse_route(text: str, *, allow_statement: bool = True) -> Route:
    """LLM 응답을 Route 로 바꾼다. 형식이 틀리거나 근거가 부족하면 simple."""
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return Route()
    try:
        data = json.loads(m.group())
    except json.JSONDecodeError:
        return Route()
    if not isinstance(data, dict):
        return Route()
    kind = data.get("route")
    if kind == "statement":
        reply = str(data.get("reply") or "").strip()
        return Route("statement", reply=reply[:400]) if reply and allow_statement else Route()
    if kind == "complex":
        raw = data.get("plan")
        steps = [_clip(str(s), PLAN_STEP_CLIP) for s in raw if str(s).strip()] if isinstance(raw, list) else []
        steps = steps[:MAX_PLAN_STEPS]
        # 단계가 하나뿐이면 계획이 군더더기이므로 단순 요청으로 본다
        return Route("complex", plan=steps) if len(steps) >= MIN_PLAN_STEPS else Route()
    return Route()


def prior_history(history: List[BaseMessage], user_input: str) -> List[BaseMessage]:
    """이번 사용자 메시지는 이미 DB(=history)에 저장돼 있으므로 마지막에 있으면 떼어 '이전 대화'만 남긴다."""
    if history and isinstance(history[-1], HumanMessage) and history[-1].content == user_input:
        return history[:-1]
    return history


def should_route(user_input: str, headless: bool) -> bool:
    """예약 실행(headless)은 사용자가 기다리지 않으므로 라우팅하지 않는다."""
    return not headless and bool(user_input.strip())


def statement_allowed(user_input: str, history: List[BaseMessage]) -> bool:
    return bool(history) and 0 < len(user_input.strip()) <= STATEMENT_MAX_CHARS


async def route_request(user_input: str, history: List[BaseMessage], skills: Optional[List[str]] = None) -> Route:
    """요청을 분류한다. 실패하면 simple."""
    try:
        from app.agent.react_agent import AgentRunner
        from app.services.memory_extractor import _content_text

        llm = AgentRunner(tools=[]).llm
        prompt = render(
            "request_router",
            context=_context(history),
            message=_clip(user_input, MESSAGE_CLIP),
            skills="\n".join(skills) if skills else "(없음)",
        )
        resp = await asyncio.wait_for(llm.ainvoke(prompt), ROUTE_TIMEOUT_SECONDS)
        return parse_route(_content_text(resp.content), allow_statement=statement_allowed(user_input, history))
    except Exception as e:
        logger.warning("[router] 분류 실패 — 단순 요청으로 처리: %s", e)
        return Route()

"""USER.md: 사용자의 성향·배경을 한 문서로 합쳐 영구 보관한다 (user_profiles). 프롬프트: prompts/memory_profile.md, memory_profile_merge.md.

사실(semantic)·작업 방식(procedural) 메모리를 사람이 읽는 한 문서로 합치고(유사한 내용은 하나로), 에이전트는 이 문서를 프롬프트로 받는다.
합친 뒤에 새로 저장된 메모리만 따로 프롬프트에 넣어, 같은 내용이 두 번 들어가지 않게 한다. 합치기는 미리보기를 거쳐 사용자가 저장해야 적용된다.
"""
import asyncio
import re
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import render
from app.models.memory import Memory, UserProfile

MAX_PROFILE_CHARS = 4000
MAX_SOURCE_ITEMS = 200
LLM_TIMEOUT_SECONDS = 90


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def clean_markdown(text: str) -> str:
    """LLM 응답에서 코드 블록 표시를 벗기고 길이를 제한한다."""
    t = (text or "").strip()
    m = re.match(r"^```(?:markdown|md)?\s*\n(.*?)\n```\s*$", t, re.DOTALL)
    if m:
        t = m.group(1).strip()
    return t[:MAX_PROFILE_CHARS].rstrip()


async def get_profile(user_id: str, db: AsyncSession) -> Optional[UserProfile]:
    return (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalar_one_or_none()


async def save_profile(user_id: str, content: str, merged: bool, db: AsyncSession) -> UserProfile:
    """문서를 저장한다. merged=True 면 지금까지의 사실·작업 방식 메모리를 이 문서에 합친 것으로 표시한다."""
    text = (content or "").strip()[:MAX_PROFILE_CHARS]
    row = await get_profile(user_id, db)
    if row is None:
        row = UserProfile(user_id=user_id, content=text, merged_at=_now() if merged else None)
        db.add(row)
    else:
        row.content = text
        if merged:
            row.merged_at = _now()
    await db.commit()
    await db.refresh(row)
    return row


def is_covered(m: Memory, profile: Optional[UserProfile]) -> bool:
    """이 메모리가 이미 USER.md 에 합쳐졌는지: 문서가 있고, 합친 시각 이후에 바뀌지 않았으면 True."""
    if profile is None or not (profile.content or "").strip() or profile.merged_at is None:
        return False
    changed = m.updated_at or m.created_at
    if changed is None:
        return False
    if changed.tzinfo:
        changed = changed.astimezone(timezone.utc).replace(tzinfo=None)
    return changed <= profile.merged_at


async def source_memories(user_id: str, db: AsyncSession) -> List[Memory]:
    """USER.md 에 합칠 대상: 활성 상태이고 유효기간이 지나지 않은 사실·작업 방식 메모리 (오래된 것부터)."""
    from app.services.memory_service import not_expired

    rows = (
        await db.execute(
            select(Memory)
            .where(Memory.user_id == user_id, Memory.is_active == True, not_expired(), Memory.memory_type.in_(("semantic", "procedural")))  # noqa: E712
            .order_by(Memory.updated_at.asc())
            .limit(MAX_SOURCE_ITEMS)
        )
    ).scalars().all()
    return list(rows)


def _lines(items: List[Memory], with_key: bool) -> str:
    if not items:
        return "(없음)"
    return "\n".join(f"- {m.key}: {m.value}" if with_key else f"- {m.value}" for m in items)


async def propose(user_id: str, db: AsyncSession) -> str:
    """현재 USER.md 와 사실·작업 방식 메모리를 합친 새 문서를 LLM 으로 만든다 (저장하지 않는다)."""
    from app.agent.react_agent import AgentRunner
    from app.services.memory_extractor import _content_text

    profile = await get_profile(user_id, db)
    items = await source_memories(user_id, db)
    prompt = render(
        "memory_profile_merge",
        current=(profile.content.strip() if profile and profile.content.strip() else "(없음)"),
        facts=_lines([m for m in items if m.memory_type == "semantic"], True),
        procedures=_lines([m for m in items if m.memory_type == "procedural"], False),
        max_chars=MAX_PROFILE_CHARS,
    )
    resp = await asyncio.wait_for(AgentRunner(tools=[]).llm.ainvoke(prompt), LLM_TIMEOUT_SECONDS)
    return clean_markdown(_content_text(resp.content))

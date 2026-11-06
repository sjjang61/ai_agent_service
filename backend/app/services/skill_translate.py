"""스킬 문서(마크다운)를 한국어로 번역한다. 긴 문서는 코드 블록을 자르지 않도록 나눠 병렬로 번역한다. 프롬프트는 prompts/skill_translate.md."""
import asyncio
import logging
import re
import hashlib

from app.agent.prompts import render

logger = logging.getLogger(__name__)

CHUNK_CHARS = 5000
MAX_CHARS = 30000
CHUNK_TIMEOUT_SECONDS = 120
PARALLEL = 3


def split_chunks(text: str, limit: int = CHUNK_CHARS) -> list[str]:
    """문단(빈 줄) 경계에서 limit 글자 안팎으로 나눈다. 코드 블록(```) 안에서는 자르지 않는다."""
    chunks: list[str] = []
    cur: list[str] = []
    size = 0
    in_fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        cur.append(line)
        size += len(line) + 1
        if size >= limit and not in_fence and not line.strip():
            chunks.append("\n".join(cur).strip("\n"))
            cur, size = [], 0
    if "".join(cur).strip():
        chunks.append("\n".join(cur).strip("\n"))
    return chunks


def clean_output(text: str) -> str:
    """모델이 전체를 ```markdown 으로 감싼 경우 벗긴다."""
    t = text.strip()
    m = re.match(r"^```(?:markdown|md)?\s*\n(.*)\n```\s*$", t, re.DOTALL)
    return m.group(1).strip() if m else t


MAX_SAVED_PER_USER = 300


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def get_saved(db, user_id: str, text: str):
    """저장된 번역 기록(같은 원문)을 찾는다. 없으면 None."""
    from sqlalchemy import select

    from app.models.skill_translation import SkillTranslation

    r = await db.execute(
        select(SkillTranslation).where(SkillTranslation.user_id == user_id, SkillTranslation.content_hash == content_hash(text))
    )
    return r.scalar_one_or_none()


async def save_translation(db, user_id: str, text: str, translated: str, truncated: bool):
    """번역 기록을 저장(같은 원문이 있으면 덮어씀)하고 오래된 기록은 정리한다."""
    from datetime import datetime, timezone

    from sqlalchemy import delete, select

    from app.models.skill_translation import SkillTranslation

    row = await get_saved(db, user_id, text)
    if row is None:
        row = SkillTranslation(user_id=user_id, content_hash=content_hash(text), translated=translated, truncated=truncated)
        db.add(row)
    else:
        row.translated, row.truncated, row.created_at = translated, truncated, datetime.now(timezone.utc)
    await db.commit()
    keep = (
        await db.execute(
            select(SkillTranslation.id).where(SkillTranslation.user_id == user_id)
            .order_by(SkillTranslation.created_at.desc()).limit(MAX_SAVED_PER_USER)
        )
    ).scalars().all()
    await db.execute(delete(SkillTranslation).where(SkillTranslation.user_id == user_id, SkillTranslation.id.notin_(keep)))
    await db.commit()
    await db.refresh(row)
    return row


async def translate_to_korean(text: str) -> dict:
    """LLM 으로 번역한다. {"content": 번역문, "truncated": 일부만 번역했는지}. 실패하면 예외."""
    from app.agent.react_agent import AgentRunner
    from app.services.memory_extractor import _content_text

    llm = AgentRunner(tools=[]).llm
    truncated = len(text) > MAX_CHARS
    chunks = split_chunks(text[:MAX_CHARS])
    sem = asyncio.Semaphore(PARALLEL)

    async def one(chunk: str) -> str:
        async with sem:
            resp = await asyncio.wait_for(llm.ainvoke(render("skill_translate", text=chunk)), CHUNK_TIMEOUT_SECONDS)
            return clean_output(_content_text(resp.content))

    parts = await asyncio.gather(*(one(c) for c in chunks))
    content = "\n\n".join(p for p in parts if p)
    if not content:
        raise RuntimeError("empty translation")
    return {"content": content, "truncated": truncated}

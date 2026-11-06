"""스킬 문서(마크다운)를 한국어로 번역한다. 긴 문서는 코드 블록을 자르지 않도록 나눠 병렬로 번역한다. 프롬프트는 prompts/skill_translate.md."""
import asyncio
import logging
import re
from collections import OrderedDict

from app.agent.prompts import render

logger = logging.getLogger(__name__)

CHUNK_CHARS = 5000
MAX_CHARS = 30000
CHUNK_TIMEOUT_SECONDS = 120
PARALLEL = 3
_CACHE_MAX = 64
# (skill_id, path, 수정 시각, 크기) -> 번역 결과
_cache: "OrderedDict[tuple, dict]" = OrderedDict()


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


async def translate_to_korean(text: str, cache_key: tuple) -> dict:
    """{"content": 번역문, "truncated": 일부만 번역했는지}. 실패하면 예외."""
    if cache_key in _cache:
        _cache.move_to_end(cache_key)
        return _cache[cache_key]
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
    result = {"content": "\n\n".join(p for p in parts if p), "truncated": truncated}
    _cache[cache_key] = result
    while len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)
    return result

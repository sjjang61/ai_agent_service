"""단기 메모리를 비슷한 내용끼리 묶고(그룹핑), 한 그룹의 중복을 합친다(병합). 프롬프트: prompts/short_memory_group.md, short_memory_merge.md.

그룹핑은 보기만 하고 데이터를 바꾸지 않는다. 병합은 미리보기를 거쳐 사용자가 확인한 뒤에만 적용한다.
"""
import asyncio
import hashlib
import json
import logging
import re
import time

from app.agent.prompts import render

logger = logging.getLogger(__name__)

LLM_TIMEOUT_SECONDS = 60
MAX_GROUP_ITEMS = 120      # 한 번에 묶는 항목 수 상한
MAX_MERGED = 8
_KEY_RE = re.compile(r"[^a-z0-9_]+")
_cache: dict[str, tuple[float, list]] = {}
CACHE_SECONDS = 600


def _lines(items: list[dict]) -> str:
    return "\n".join(f"[{i}] (대화: {(it.get('conversation_title') or '제목 없음')[:40]}) {it['key']}: {it['value']}" for i, it in enumerate(items))


async def _ask(prompt: str) -> str:
    from app.agent.react_agent import AgentRunner
    from app.services.memory_extractor import _content_text

    resp = await asyncio.wait_for(AgentRunner(tools=[]).llm.ainvoke(prompt), LLM_TIMEOUT_SECONDS)
    return _content_text(resp.content)


def _json(text: str):
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except ValueError:
        return None


def parse_groups(text: str, n: int) -> list[dict]:
    """LLM 응답 → [{title, indices}]. 범위를 벗어난 번호·중복은 버리고, 빠진 항목은 항목 1개짜리 그룹으로 보충한다."""
    data = _json(text)
    seen: set[int] = set()
    out: list[dict] = []
    for g in (data or {}).get("groups", []) if isinstance(data, dict) else []:
        if not isinstance(g, dict):
            continue
        idx = []
        for i in g.get("items") or []:
            if isinstance(i, int) and 0 <= i < n and i not in seen:
                seen.add(i)
                idx.append(i)
        if idx:
            out.append({"title": " ".join(str(g.get("title") or "").split())[:40], "indices": sorted(idx)})
    out += [{"title": "", "indices": [i]} for i in range(n) if i not in seen]
    return out


def parse_merged(text: str, max_items: int = MAX_MERGED) -> list[dict]:
    """LLM 응답 → [{key, value}] (key 는 snake_case 로 정리, 중복·빈 값 제거, 최대 max_items)."""
    data = _json(text)
    out: list[dict] = []
    used: set[str] = set()
    for it in (data or {}).get("items", []) if isinstance(data, dict) else []:
        if not isinstance(it, dict):
            continue
        key = _KEY_RE.sub("_", str(it.get("key", "")).strip().lower()).strip("_")[:100]
        value = " ".join(str(it.get("value", "")).split())[:500]
        if not key or not value or key in used:
            continue
        used.add(key)
        out.append({"key": key, "value": value})
        if len(out) >= max_items:
            break
    return out


async def group_items(items: list[dict]) -> list[dict]:
    """[{title, indices}]. 같은 항목 집합은 10분간 결과를 재사용한다. LLM 이 실패하면 예외."""
    items = items[:MAX_GROUP_ITEMS]
    sig = hashlib.sha1(json.dumps([(i["conversation_id"], i["key"], i["value"]) for i in items], ensure_ascii=False).encode()).hexdigest()
    hit = _cache.get(sig)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    groups = parse_groups(await _ask(render("short_memory_group", items=_lines(items))), len(items))
    _cache[sig] = (time.monotonic(), groups)
    if len(_cache) > 50:
        _cache.pop(next(iter(_cache)))
    return groups


async def merge_group(items: list[dict]) -> list[dict]:
    """한 그룹의 항목을 합친 [{key, value}]. 결과가 비면 예외."""
    merged = parse_merged(await _ask(render("short_memory_merge", items=_lines(items), max_items=MAX_MERGED)))
    if not merged:
        raise ValueError("합친 결과를 만들지 못했습니다")
    return merged


def unique_key(key: str, taken: set[str]) -> str:
    """이미 쓰는 key 와 겹치면 숫자를 붙인다."""
    if key not in taken:
        return key
    n = 2
    while f"{key}_{n}" in taken:
        n += 1
    return f"{key}_{n}"

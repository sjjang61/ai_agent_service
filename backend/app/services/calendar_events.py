"""단기 메모리에 적힌 날짜 있는 일정을 캘린더 이벤트로 추출한다. 프롬프트: prompts/calendar_extract.md.

항목 내용이 같으면 LLM 을 다시 부르지 않도록 사용자별로 결과를 캐시한다(내용이 바뀌면 자동으로 새로 추출).
"""
import asyncio
import hashlib
import json
import re
import time
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from app.agent.prompts import render
from app.config import settings

LLM_TIMEOUT_SECONDS = 60
MAX_ITEMS = 80
CACHE_SECONDS = 3600
_cache: dict[str, tuple[float, list]] = {}
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _today() -> date:
    return datetime.now(ZoneInfo(settings.SCHEDULER_DEFAULT_TIMEZONE)).date()


def _d(v) -> Optional[str]:
    try:
        return date.fromisoformat(str(v).strip()[:10]).isoformat()
    except ValueError:
        return None


def parse_events(text: str, items: list[dict]) -> list[dict]:
    """LLM 응답 → 검증된 이벤트. 날짜가 틀리면 버리고, 종료일이 시작일보다 앞서면 시작일로 맞춘다."""
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    try:
        data = json.loads(m.group()) if m else None
    except ValueError:
        data = None
    out: list[dict] = []
    for e in (data or {}).get("events", []) if isinstance(data, dict) else []:
        if not isinstance(e, dict):
            continue
        start = _d(e.get("start_date"))
        title = " ".join(str(e.get("title") or "").split())[:40]
        if not start or not title:
            continue
        end = _d(e.get("end_date")) or start
        if end < start:
            end = start
        src = e.get("source")
        item = items[src] if isinstance(src, int) and 0 <= src < len(items) else None
        st, et = str(e.get("start_time") or ""), str(e.get("end_time") or "")
        out.append({
            "title": title,
            "start_date": start,
            "end_date": end,
            "start_time": st if _TIME_RE.match(st) else "",
            "end_time": et if _TIME_RE.match(et) else "",
            "note": " ".join(str(e.get("note") or "").split())[:200],
            "conversation_id": item["conversation_id"] if item else None,
            "conversation_title": (item.get("conversation_title") if item else None),
            "key": item["key"] if item else None,
        })
    out.sort(key=lambda e: (e["start_date"], e["start_time"], e["title"]))
    for i, e in enumerate(out):
        e["id"] = f"{e['start_date']}-{i}"
    return out


async def _ask(prompt: str) -> str:
    from app.agent.react_agent import AgentRunner
    from app.services.memory_extractor import _content_text

    resp = await asyncio.wait_for(AgentRunner(tools=[]).llm.ainvoke(prompt), LLM_TIMEOUT_SECONDS)
    return _content_text(resp.content)


async def extract_events(user_id: str, items: list[dict], refresh: bool = False) -> list[dict]:
    items = items[:MAX_ITEMS]
    if not items:
        return []
    today = _today()
    sig = hashlib.sha1(json.dumps([user_id, today.isoformat(), [(i["conversation_id"], i["key"], i["value"]) for i in items]], ensure_ascii=False).encode()).hexdigest()
    hit = _cache.get(sig)
    if hit and not refresh and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    lines = "\n".join(f"[{n}] {i['key']}: {i['value']}" for n, i in enumerate(items))
    events = parse_events(await _ask(render("calendar_extract", today=today.isoformat(), items=lines)), items)
    _cache[sig] = (time.monotonic(), events)
    if len(_cache) > 100:
        _cache.pop(next(iter(_cache)))
    return events

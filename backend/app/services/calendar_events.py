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
            "memory_id": item.get("memory_id") if item else None,
            "source_kind": item.get("source_kind", "short") if item else "short",
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
    sig = hashlib.sha1(json.dumps([user_id, today.isoformat(), [(i["conversation_id"], i["key"], i["value"], i.get("valid_until")) for i in items]], ensure_ascii=False).encode()).hexdigest()
    hit = _cache.get(sig)
    if hit and not refresh and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    lines = "\n".join(
        f"[{n}] {i['key']}: {i['value']}" + (f" (유효기간 종료일: {i['valid_until']})" if i.get("valid_until") else "")
        for n, i in enumerate(items)
    )
    events = parse_events(await _ask(render("calendar_extract", today=today.isoformat(), items=lines)), items)
    _cache[sig] = (time.monotonic(), events)
    if len(_cache) > 100:
        _cache.pop(next(iter(_cache)))
    return events


_DATE_HINT = re.compile(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}|\d{1,2}\s*월\s*\d{1,2}\s*일|\d{1,2}/\d{1,2}|\d{4}\s*년")


def memory_items(memories: list) -> list[dict]:
    """장기 메모리 중 시작·종료 일정이 있는 것만 추출 입력으로 만든다(유효기간이 있거나 본문에 날짜 표현이 있는 사실·사례).
    캘린더 화면에서 직접 추가해 메모리에 연결한 것(calendar_ 키)은 이미 일정으로 있으므로 제외한다."""
    out = []
    for m in memories:
        if (m.key or "").startswith("calendar_") or m.memory_type == "procedural":
            continue
        if not (m.expires_at or _DATE_HINT.search(m.value or "")):
            continue
        valid = None
        if m.expires_at:  # 만료는 종료일 다음 날 0시(현지)라 하루를 되돌려 종료일로 보여 준다
            tz = ZoneInfo(settings.SCHEDULER_DEFAULT_TIMEZONE)
            from datetime import timedelta, timezone
            valid = (m.expires_at.replace(tzinfo=timezone.utc).astimezone(tz) - timedelta(seconds=1)).date().isoformat()
        out.append({
            "conversation_id": None, "conversation_title": "장기 메모리", "key": m.key, "value": m.value,
            "valid_until": valid, "source_kind": "memory", "memory_id": m.id,
        })
    return out

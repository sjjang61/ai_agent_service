"""Episodes: 날짜별 일지 (memory_journals, 영구 보관).

그날 저장된 사건·해결 사례(episodic 메모리)가 한 줄씩 쌓인다 (MemoryService.create_memory 가 호출). 사례 메모리는 시간이 지나면 중요도가 줄어
정리되지만 일지는 지우지 않는다. 사용자가 날짜별로 직접 고치거나 메모를 덧붙일 수 있다.
"""
import re
from datetime import datetime, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.memory import Memory, MemoryJournal

DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_CONTENT_CHARS = 20000


def valid_day(day: str) -> bool:
    try:
        datetime.strptime(day or "", "%Y-%m-%d")
        return bool(DAY_RE.match(day))
    except ValueError:
        return False


def local_time(dt: Optional[datetime]) -> datetime:
    """UTC naive(또는 aware) 시각을 서버 기본 시간대의 시각으로."""
    tz = ZoneInfo(settings.SCHEDULER_DEFAULT_TIMEZONE)
    if dt is None:
        return datetime.now(tz)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)


def episode_line(m: Memory) -> str:
    """에피소드 메모리 하나를 일지 한 줄로: `- 14:30 제목 — 상황 → 해결 (결과)`."""
    when = local_time(m.occurred_at or m.created_at)
    d = m.detail or {}
    parts = " → ".join(x for x in (d.get("situation", ""), d.get("resolution", "")) if x)
    line = f"- {when.strftime('%H:%M')} {m.value}" + (f" — {parts}" if parts else "")
    if d.get("outcome"):
        line += f" ({d['outcome']})"
    return line


async def get_day(user_id: str, day: str, db: AsyncSession) -> Optional[MemoryJournal]:
    return (await db.execute(select(MemoryJournal).where(MemoryJournal.user_id == user_id, MemoryJournal.day == day))).scalar_one_or_none()


async def append_line(user_id: str, day: str, line: str, db: AsyncSession) -> MemoryJournal:
    """그날 일지에 한 줄 덧붙인다 (같은 줄이 이미 있으면 그대로)."""
    row = await get_day(user_id, day, db)
    if row is None:
        row = MemoryJournal(user_id=user_id, day=day, content=line)
        db.add(row)
    elif line not in (row.content or "").splitlines():
        row.content = ((row.content or "").rstrip() + "\n" + line).strip()[:MAX_CONTENT_CHARS]
    await db.commit()
    await db.refresh(row)
    return row


async def record_episode(user_id: str, m: Memory, db: AsyncSession) -> None:
    """에피소드 메모리가 저장되면 그 날짜 일지에 한 줄 남긴다."""
    when = local_time(m.occurred_at or m.created_at)
    await append_line(user_id, when.strftime("%Y-%m-%d"), episode_line(m), db)


async def save_day(user_id: str, day: str, content: str, db: AsyncSession) -> Optional[MemoryJournal]:
    """그날 일지를 통째로 저장한다. 내용이 비면 그날 일지를 지우고 None."""
    text = (content or "").strip()[:MAX_CONTENT_CHARS]
    row = await get_day(user_id, day, db)
    if not text:
        if row is not None:
            await db.delete(row)
            await db.commit()
        return None
    if row is None:
        row = MemoryJournal(user_id=user_id, day=day, content=text)
        db.add(row)
    else:
        row.content = text
    await db.commit()
    await db.refresh(row)
    return row


async def backfill(user_id: str, db: AsyncSession) -> int:
    """일지가 하나도 없는데 이미 저장된 사례 메모리가 있으면, 그 사례들을 날짜별 일지로 옮긴다 (처음 한 번)."""
    n = (await db.execute(select(func.count()).select_from(MemoryJournal).where(MemoryJournal.user_id == user_id))).scalar_one()
    if n:
        return 0
    rows = (
        await db.execute(select(Memory).where(Memory.user_id == user_id, Memory.memory_type == "episodic").order_by(Memory.occurred_at.asc(), Memory.created_at.asc()))
    ).scalars().all()
    added = 0
    for m in rows:
        when = local_time(m.occurred_at or m.created_at)
        day, line = when.strftime("%Y-%m-%d"), episode_line(m)
        row = await get_day(user_id, day, db)
        if row is None:
            db.add(MemoryJournal(user_id=user_id, day=day, content=line))
            await db.flush()
        elif line not in (row.content or "").splitlines():
            row.content = (row.content.rstrip() + "\n" + line)[:MAX_CONTENT_CHARS]
        added += 1
    await db.commit()
    return added


async def list_days(user_id: str, db: AsyncSession, limit: int = 30, before: Optional[str] = None) -> List[MemoryJournal]:
    """최근 날짜부터. before(YYYY-MM-DD)가 있으면 그 날짜보다 이전만."""
    q = select(MemoryJournal).where(MemoryJournal.user_id == user_id)
    if before and valid_day(before):
        q = q.where(MemoryJournal.day < before)
    return list((await db.execute(q.order_by(MemoryJournal.day.desc()).limit(max(1, min(limit, 200))))).scalars().all())


async def delete_day(user_id: str, day: str, db: AsyncSession) -> bool:
    res = await db.execute(delete(MemoryJournal).where(MemoryJournal.user_id == user_id, MemoryJournal.day == day))
    await db.commit()
    return (res.rowcount or 0) > 0

"""캘린더 API: 단기 메모리에 기억된 일정을 이벤트로 돌려준다."""
import logging
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.calendar_event import CalendarEvent as CalendarEventRow
from app.schemas.memory import MemoryCreate, MemoryUpdate
from app.services.memory_service import MemoryService

from app.api.memory import _short_items
from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.services import calendar_events

logger = logging.getLogger(__name__)
router = APIRouter()


class CalendarEvent(BaseModel):
    id: str
    title: str
    start_date: str
    end_date: str
    start_time: str = ""
    end_time: str = ""
    note: str = ""
    conversation_id: Optional[str] = None
    conversation_title: Optional[str] = None
    key: Optional[str] = None
    manual: bool = False        # 사용자가 직접 추가한 일정(수정·삭제 가능)
    in_memory: bool = False     # 메모리(사실)에도 저장돼 있음


_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class EventInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    start_date: str
    end_date: Optional[str] = None
    start_time: str = ""
    end_time: str = ""
    note: str = ""
    save_to_memory: bool = False   # True 면 메모리(사실)에도 저장 — 일정이 끝나는 날까지 에이전트가 참고한다

    @field_validator("start_date", "end_date")
    @classmethod
    def _date(cls, v):
        if v in (None, ""):
            return None
        try:
            return date.fromisoformat(v).isoformat()
        except ValueError:
            raise ValueError("날짜는 YYYY-MM-DD 형식이어야 합니다")

    @field_validator("start_time", "end_time")
    @classmethod
    def _time(cls, v):
        if v and not _TIME.match(v):
            raise ValueError("시각은 HH:MM 형식이어야 합니다")
        return v or ""

    @model_validator(mode="after")
    def _range(self):
        self.end_date = self.end_date or self.start_date
        if self.end_date < self.start_date:
            raise ValueError("종료일이 시작일보다 빠릅니다")
        self.title = " ".join(self.title.split())
        return self


def _row_to_event(r: CalendarEventRow) -> dict:
    return {
        "id": f"m-{r.id}", "title": r.title, "start_date": r.start_date, "end_date": r.end_date,
        "start_time": r.start_time or "", "end_time": r.end_time or "", "note": r.note or "",
        "manual": True, "in_memory": bool(r.memory_id),
    }


def _memory_text(inp: EventInput) -> str:
    period = inp.start_date if inp.end_date == inp.start_date else f"{inp.start_date}~{inp.end_date}"
    t = f" {inp.start_time}" + (f"~{inp.end_time}" if inp.end_time else "") if inp.start_time else ""
    return f"{inp.title} ({period}{t})" + (f" - {inp.note}" if inp.note else "")


def _expires(end_date: str) -> datetime:
    """종료일 24시(다음 날 0시) — UTC naive."""
    tz = ZoneInfo(settings.SCHEDULER_DEFAULT_TIMEZONE)
    end = datetime.combine(date.fromisoformat(end_date) + timedelta(days=1), time.min, tzinfo=tz)
    return end.astimezone(timezone.utc).replace(tzinfo=None)


async def _sync_memory(user_id: str, row: CalendarEventRow, inp: EventInput, db: AsyncSession):
    """메모리에 저장하도록 요청됐으면 만들거나 갱신하고, 아니면 연결된 메모리를 지운다."""
    if not inp.save_to_memory:
        if row.memory_id:
            await MemoryService.delete_memory(user_id, row.memory_id, db)
            row.memory_id = None
        return
    expires = _expires(inp.end_date)
    if expires <= datetime.now(timezone.utc).replace(tzinfo=None):
        return  # 이미 지난 일정은 메모리에 남기지 않는다
    text = _memory_text(inp)
    if row.memory_id and await MemoryService.get_memory(user_id, row.memory_id, db):
        await MemoryService.update_memory(user_id, row.memory_id, MemoryUpdate(value=text, expires_at=expires), db)
        return
    mem = await MemoryService.create_memory(
        user_id,
        MemoryCreate(key=f"calendar_{row.id[:8]}", value=text, category="fact", memory_type="semantic", importance=6, expires_at=expires),
        db,
        source="manual",
    )
    row.memory_id = mem.id


async def _owned(event_id: str, user_id: str, db: AsyncSession) -> CalendarEventRow:
    row = (await db.execute(select(CalendarEventRow).where(CalendarEventRow.id == event_id, CalendarEventRow.user_id == user_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다")
    return row


@router.post("/manual", response_model=CalendarEvent)
async def create_event(inp: EventInput, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    row = CalendarEventRow(user_id=current_user.id, title=inp.title, start_date=inp.start_date, end_date=inp.end_date,
                           start_time=inp.start_time, end_time=inp.end_time, note=inp.note)
    db.add(row)
    await db.flush()
    await _sync_memory(current_user.id, row, inp, db)
    await db.commit()
    return _row_to_event(row)


@router.put("/manual/{event_id}", response_model=CalendarEvent)
async def update_event(event_id: str, inp: EventInput, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    row = await _owned(event_id, current_user.id, db)
    row.title, row.start_date, row.end_date = inp.title, inp.start_date, inp.end_date
    row.start_time, row.end_time, row.note = inp.start_time, inp.end_time, inp.note
    await _sync_memory(current_user.id, row, inp, db)
    await db.commit()
    return _row_to_event(row)


@router.delete("/manual/{event_id}", status_code=204)
async def delete_event(event_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    row = await _owned(event_id, current_user.id, db)
    if row.memory_id:
        await MemoryService.delete_memory(current_user.id, row.memory_id, db)
    await db.delete(row)
    await db.commit()


@router.get("/events", response_model=List[CalendarEvent])
async def list_events(
    refresh: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    rows = (await db.execute(select(CalendarEventRow).where(CalendarEventRow.user_id == current_user.id))).scalars().all()
    manual = [_row_to_event(r) for r in rows]
    items = await _short_items(current_user.id, db)
    try:
        extracted = await calendar_events.extract_events(current_user.id, items, refresh=refresh)
    except Exception as e:  # noqa: BLE001
        logger.warning("[calendar] 일정 추출 실패: %s", e)
        if manual:  # 직접 추가한 일정은 추출이 실패해도 보여 준다
            return sorted(manual, key=lambda e: (e["start_date"], e["start_time"]))
        raise HTTPException(status_code=502, detail=f"일정을 추출하지 못했습니다: {type(e).__name__}: {str(e)[:150]}")
    return sorted(manual + extracted, key=lambda e: (e["start_date"], e["start_time"]))

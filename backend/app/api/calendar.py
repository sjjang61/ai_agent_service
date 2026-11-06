"""캘린더 API: 단기 메모리에 기억된 일정을 이벤트로 돌려준다."""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

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


@router.get("/events", response_model=List[CalendarEvent])
async def list_events(
    refresh: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    items = await _short_items(current_user.id, db)
    try:
        return await calendar_events.extract_events(current_user.id, items, refresh=refresh)
    except Exception as e:  # noqa: BLE001
        logger.warning("[calendar] 일정 추출 실패: %s", e)
        raise HTTPException(status_code=502, detail=f"일정을 추출하지 못했습니다: {type(e).__name__}: {str(e)[:150]}")

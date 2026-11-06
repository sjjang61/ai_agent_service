import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text

from app.db.base import Base


class CalendarEvent(Base):
    """사용자가 직접 추가한 캘린더 일정. memory_id 가 있으면 같은 내용이 메모리(사실)에도 저장돼 있다."""

    __tablename__ = "calendar_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    start_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    end_date = Column(String(10), nullable=False)
    start_time = Column(String(5), nullable=False, default="")  # HH:MM 또는 ""
    end_time = Column(String(5), nullable=False, default="")
    note = Column(Text, nullable=True)
    memory_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

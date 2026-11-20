import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    UniqueConstraint,
)

from app.db.base import Base


class Memory(Base):
    """Long-term memory storage for user information and preferences."""

    __tablename__ = "memories"
    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_memories_user_key"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    category = Column(
        String(50), nullable=False, default="general"
    )  # preference, fact, instruction, general
    key = Column(String(200), nullable=False)
    value = Column(Text, nullable=False)
    tags = Column(JSON, default=list)
    source = Column(
        String(20), default="manual"
    )  # manual | auto_extracted | agent
    importance = Column(Integer, default=5)  # 1-10
    # semantic(사실) | episodic(사건·해결 사례) | procedural(작업 방식 지침)
    memory_type = Column(String(20), nullable=False, default="semantic", index=True)
    occurred_at = Column(DateTime, nullable=True)  # episodic: 사건이 일어난 시점 (UTC naive)
    detail = Column(JSON, nullable=True)  # episodic: {situation, resolution, outcome}
    # 유효기간이 있는 사실(여행·예약·마감 같은 일정): 이 시각(UTC naive)이 지나면 프롬프트에서 빠지고 정리된다. NULL 이면 영구
    expires_at = Column(DateTime, nullable=True)
    conversation_id = Column(String(36), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class UserProfile(Base):
    """USER.md: 사용자의 성향·배경을 한 문서로 합쳐 둔 영구 프로필 (마크다운). 사용자당 1개.
    merged_at 은 사실·작업 방식 메모리를 이 문서로 마지막에 합친 시각이다. 그 뒤에 새로 저장된 메모리만 프롬프트에 따로 넣는다."""

    __tablename__ = "user_profiles"

    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    content = Column(Text, nullable=False, default="")
    merged_at = Column(DateTime, nullable=True)  # UTC naive
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class MemoryJournal(Base):
    """Episodes: 날짜별 일지 (영구 보관). 그날 저장된 사건·해결 사례가 한 줄씩 쌓이고, 사용자가 직접 고칠 수도 있다.
    사례 메모리(episodic)는 시간이 지나면 중요도가 줄어 정리되지만, 일지는 지우지 않는다."""

    __tablename__ = "memory_journals"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_memory_journal_user_day"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    day = Column(String(10), nullable=False)  # YYYY-MM-DD (SCHEDULER_DEFAULT_TIMEZONE 기준)
    content = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

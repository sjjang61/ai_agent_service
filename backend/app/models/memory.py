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
    conversation_id = Column(String(36), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

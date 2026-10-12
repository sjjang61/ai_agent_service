import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey

from app.db.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), default="New Conversation")
    llm_provider = Column(String(50), default="anthropic")
    model_name = Column(String(100), default="claude-opus-4-5")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

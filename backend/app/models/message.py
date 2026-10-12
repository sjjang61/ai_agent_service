import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Text

from app.db.base import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user | assistant | system
    content = Column(Text, nullable=False)
    agent_steps = Column(JSON, default=list)
    tool_calls = Column(JSON, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    metadata_ = Column("metadata", JSON, default=dict)

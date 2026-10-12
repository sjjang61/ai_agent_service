import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON, Text, Integer

from app.db.base import Base


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String(36), ForeignKey("messages.id"), nullable=True, index=True)
    tool_name = Column(String(200), nullable=False)
    tool_input = Column(JSON, default=dict)
    tool_output = Column(Text, nullable=True)
    duration_ms = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

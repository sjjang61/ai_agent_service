import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, JSON, String, Text

from app.db.base import Base


class Message(Base):
    __tablename__ = "messages"
    # 대화방별 시간순 조회(WHERE conversation_id = ? ORDER BY created_at)를 인덱스 순서로 읽는다.
    # 없으면 agent_steps 같은 큰 JSON 열까지 정렬하다 'Out of sort memory'(MySQL 1038)가 난다.
    __table_args__ = (Index("ix_messages_conversation_created", "conversation_id", "created_at"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user | assistant | system
    content = Column(Text, nullable=False)
    agent_steps = Column(JSON, default=list)
    tool_calls = Column(JSON, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    metadata_ = Column("metadata", JSON, default=dict)

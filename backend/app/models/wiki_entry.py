"""WikiEntry model for personal wiki storage."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
)

from app.db.base import Base


class WikiEntry(Base):
    """Personal wiki entries saved from chat responses."""

    __tablename__ = "wiki_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Core content
    title = Column(String(200), nullable=False)  # User-defined title
    content = Column(Text, nullable=False)       # 위키 문서 본문 (마크다운). AI 가 정리한 문서이거나, 정리 없이 저장한 원문
    summary = Column(String(500), nullable=True)  # 한두 문장 요약
    source_text = Column(Text, nullable=True)     # 정리 전 원문 (사용자가 선택한 텍스트)
    links = Column(JSON, default=list)            # 이 문서가 연결한 다른 위키 문서 id 목록 (역링크는 조회할 때 계산)

    # Metadata
    category = Column(String(50), nullable=False, default="general")  # general | work | learning | reference
    tags = Column(JSON, default=list)  # ["python", "tutorial", "api"]

    # Source tracking (optional - for future "view original" feature)
    source_message_id = Column(String(36), nullable=True)  # FK to messages.id
    source_conversation_id = Column(String(36), nullable=True)  # FK to conversations.id

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

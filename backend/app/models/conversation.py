import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from app.db.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), default="New Conversation")
    llm_provider = Column(String(50), default="anthropic")
    model_name = Column(String(100), default="claude-opus-4-5")
    # 커스텀 에이전트로 시작한 대화: 어떤 에이전트의 어떤 발행 버전인지, 빌더 미리보기(is_test)인지
    agent_id = Column(String(36), nullable=True, index=True)
    agent_version_id = Column(String(36), nullable=True)
    is_test = Column(Boolean, nullable=False, default=False)
    # 롤링 요약: 컨텍스트 창(최근 N개)에서 밀려난 오래된 메시지를 요약해 둔다
    summary = Column(Text, nullable=True)
    summary_count = Column(Integer, nullable=False, default=0)  # 요약에 반영된 메시지 수 (시간순 앞에서부터)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

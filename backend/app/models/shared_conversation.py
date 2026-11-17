import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String

from app.db.base import Base


class SharedConversation(Base):
    """대화 공유 링크. 공유한 시점의 대화를 복사해 두고(snapshot) 로그인 없이 토큰 주소로 읽게 한다.
    원본 대화가 이후 바뀌거나 삭제돼도 이미 만든 스냅샷은 그대로이며, 공유 해제나 대화 삭제 때 이 행을 지우면 링크가 끊긴다.
    스냅샷에는 사용자·어시스턴트 글과 위젯 데이터만 넣고 도구 입력/출력·첨부·참조 같은 내부 기록은 넣지 않는다."""

    __tablename__ = "shared_conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # 대화 하나에 공유 링크는 하나: 다시 공유하면 같은 주소에서 내용만 최신으로 바꾼다
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False, unique=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(64), nullable=False, unique=True)
    title = Column(String(255), nullable=False, default="")
    snapshot = Column(JSON, nullable=False, default=list)  # [{role, content, widgets, created_at}]
    message_count = Column(Integer, nullable=False, default=0)
    view_count = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime, nullable=True)  # 없으면 해제할 때까지
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

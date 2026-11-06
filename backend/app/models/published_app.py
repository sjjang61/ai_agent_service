import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from app.db.base import Base


class PublishedApp(Base):
    """배포된 웹앱. 불변 아카이브(호스트 디스크) + 앱 전용 컨테이너(요청 시 깨움) + 프록시 포트(20000번대)."""

    __tablename__ = "published_apps"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_published_app_user_name"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(String(36), nullable=True)
    name = Column(String(60), nullable=False)
    kind = Column(String(10), nullable=False, default="static")  # static | server
    proxy_port = Column(Integer, nullable=True, unique=True)  # 외부(프록시) 포트
    container_port = Column(Integer, nullable=False, default=5173)
    version = Column(Integer, nullable=False, default=1)
    artifact_size = Column(Integer, nullable=False, default=0)
    status = Column(String(10), nullable=False, default="stopped")  # stopped | starting | running | failed
    error = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    require_token = Column(Boolean, nullable=False, default=False)
    access_token = Column(String(64), nullable=False)
    container_id = Column(String(80), nullable=True)
    last_request_at = Column(DateTime, nullable=True)
    last_log = Column(Text, nullable=True)  # 컨테이너를 내릴 때 남기는 마지막 로그
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

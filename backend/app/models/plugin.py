import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint

from app.db.base import Base


class Plugin(Base):
    """GitHub 에서 설치한 플러그인 (여러 skill 을 묶은 패키지). skill 본체는 skills 테이블에 저장된다."""

    __tablename__ = "plugins"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_plugins_user_name"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String(50), nullable=True)
    source_url = Column(String(500), nullable=False)
    skill_names = Column(JSON, default=list)  # 이 플러그인이 설치한 skill 이름 목록
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

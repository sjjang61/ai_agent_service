import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text

from app.db.base import Base


class BrowserProfile(Base):
    """사용자 단위 브라우저 로그인 상태(쿠키·localStorage). sandbox 와 무관하게 재사용한다.
    state_enc 는 Playwright storage_state JSON 을 Fernet 으로 암호화한 값이다."""

    __tablename__ = "browser_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    state_enc = Column(Text().with_variant(Text(length=4294967295), "mysql"), nullable=False)
    domains = Column(JSON, nullable=False, default=list)  # [{"domain": "linkedin.com", "cookies": 12}]
    size_bytes = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

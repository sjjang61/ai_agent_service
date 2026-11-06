import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, UniqueConstraint

from app.db.base import Base


class UserToolSetting(Base):
    """사용자가 도구 목록에서 직접 켜고 끈 도구. 행이 없는 도구는 켜져 있다(기본)."""

    __tablename__ = "user_tool_settings"
    __table_args__ = (UniqueConstraint("user_id", "tool_name", name="uq_user_tool_settings_user_tool"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    tool_name = Column(String(100), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

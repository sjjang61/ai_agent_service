import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.mysql import LONGTEXT

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # DB 규약: UTC naive


class Space(Base):
    """페이지를 묶는 공간(프로젝트 작업공간)"""

    __tablename__ = "spaces"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=_now)


class Page(Base):
    """스페이스의 문서 페이지 (마크다운). deleted_at 이 있으면 휴지통."""

    __tablename__ = "pages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    space_id = Column(String(36), nullable=True, index=True)  # 공간 삭제 시 NULL 로 되돌린다
    title = Column(String(200), nullable=False, default="")
    content = Column(Text().with_variant(LONGTEXT, "mysql"), nullable=False, default="")
    is_favorite = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now, index=True)

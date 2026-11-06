import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint

from app.db.base import Base


class SkillTranslation(Base):
    """스킬 문서의 한국어 번역 기록. 원문 내용의 해시로 찾으므로 문서가 바뀌면 자동으로 무효화되고,
    스킬을 지웠다 다시 추가해도 내용이 같으면 재사용된다."""

    __tablename__ = "skill_translations"
    __table_args__ = (UniqueConstraint("user_id", "content_hash", name="uq_skill_translations_user_hash"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    content_hash = Column(String(64), nullable=False)  # 원문 sha256
    translated = Column(Text().with_variant(Text(length=4294967295), "mysql"), nullable=False)
    truncated = Column(Boolean, nullable=False, default=False)  # 길어서 앞부분만 번역했는지
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

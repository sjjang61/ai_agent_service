import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint

from app.db.base import Base


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_skills_user_name"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    source_url = Column(String(500), nullable=False)
    install_path = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

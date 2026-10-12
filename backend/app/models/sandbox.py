import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey

from app.db.base import Base


class Sandbox(Base):
    __tablename__ = "sandboxes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    container_id = Column(String(100), nullable=True)
    status = Column(String(20), default="stopped")  # running | stopped | error
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON

from app.db.base import Base


class MCPServerConfig(Base):
    __tablename__ = "mcp_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200), nullable=False)
    transport = Column(String(20), default="stdio")  # stdio | sse | streamable
    command = Column(String(500), nullable=True)
    args = Column(JSON, default=list)
    url = Column(String(500), nullable=True)
    env = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

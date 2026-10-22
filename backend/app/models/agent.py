import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # DB 규약: UTC naive


class Agent(Base):
    """사용자가 만든 커스텀 에이전트. draft_config 는 편집 중인 초안, 발행하면 agent_versions 에 스냅샷이 쌓인다."""

    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_agents_user_name"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=False, default="")
    icon = Column(String(8), nullable=False, default="🤖")
    draft_config = Column(JSON, nullable=False)
    published_version_id = Column(String(36), nullable=True)  # FK 는 두지 않는다 (순환 참조 회피)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class AgentVersion(Base):
    """발행 시점의 불변 설정 스냅샷. 채팅·예약 실행은 항상 발행된 버전을 쓴다."""

    __tablename__ = "agent_versions"
    __table_args__ = (UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_version"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    config = Column(JSON, nullable=False)
    note = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=_now)

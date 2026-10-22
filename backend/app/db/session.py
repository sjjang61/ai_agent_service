from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.db.base import Base

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"ssl": None},
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def get_session_context():
    """Async context manager for DB session (for use in tools/services)."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    from app.models import user, conversation, message, mcp_config, tool_execution, sandbox, skill, plugin, memory, scheduled_task, space, agent  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_memory_columns)
        await conn.run_sync(_ensure_conversation_columns)
        await conn.run_sync(_ensure_agent_columns)
        await conn.run_sync(_ensure_token_usage_nullable)


def _ensure_memory_columns(sync_conn) -> None:
    """create_all 은 기존 테이블에 컬럼을 추가하지 않으므로 memories 의 신규 컬럼을 보강한다.
    (alembic 마이그레이션 e5f6a1b2c3d4 와 같은 변경. 이미 적용돼 있으면 아무 일도 하지 않는다.)"""
    from sqlalchemy import inspect, text

    cols = {c["name"] for c in inspect(sync_conn).get_columns("memories")}
    if "memory_type" not in cols:
        sync_conn.execute(text("ALTER TABLE memories ADD COLUMN memory_type VARCHAR(20) NOT NULL DEFAULT 'semantic'"))
        sync_conn.execute(text("CREATE INDEX ix_memories_memory_type ON memories (memory_type)"))
        sync_conn.execute(text("UPDATE memories SET memory_type = 'procedural' WHERE category = 'instruction'"))
    if "occurred_at" not in cols:
        sync_conn.execute(text("ALTER TABLE memories ADD COLUMN occurred_at DATETIME NULL"))
    if "detail" not in cols:
        sync_conn.execute(text("ALTER TABLE memories ADD COLUMN detail JSON NULL"))


def _ensure_conversation_columns(sync_conn) -> None:
    """conversations 의 롤링 요약 컬럼 보강 (alembic f6a1b2c3d4e5 와 같은 변경)."""
    from sqlalchemy import inspect, text

    cols = {c["name"] for c in inspect(sync_conn).get_columns("conversations")}
    if "summary" not in cols:
        sync_conn.execute(text("ALTER TABLE conversations ADD COLUMN summary TEXT NULL"))
    if "summary_count" not in cols:
        sync_conn.execute(text("ALTER TABLE conversations ADD COLUMN summary_count INT NOT NULL DEFAULT 0"))


def _ensure_agent_columns(sync_conn) -> None:
    """커스텀 에이전트 연결 컬럼 보강 (alembic g7a1b2c3d4e5 와 같은 변경)."""
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    conv = {c["name"] for c in insp.get_columns("conversations")}
    if "agent_id" not in conv:
        sync_conn.execute(text("ALTER TABLE conversations ADD COLUMN agent_id VARCHAR(36) NULL"))
        sync_conn.execute(text("CREATE INDEX ix_conversations_agent_id ON conversations (agent_id)"))
    if "agent_version_id" not in conv:
        sync_conn.execute(text("ALTER TABLE conversations ADD COLUMN agent_version_id VARCHAR(36) NULL"))
    if "is_test" not in conv:
        sync_conn.execute(text("ALTER TABLE conversations ADD COLUMN is_test BOOLEAN NOT NULL DEFAULT 0"))
    task = {c["name"] for c in insp.get_columns("scheduled_tasks")}
    if "agent_id" not in task:
        sync_conn.execute(text("ALTER TABLE scheduled_tasks ADD COLUMN agent_id VARCHAR(36) NULL"))


def _ensure_token_usage_nullable(sync_conn) -> None:
    """token_usages.conversation_id 를 NULL 허용으로 (대화 삭제 후에도 사용량 기록 유지, alembic h8a1b2c3d4e5 와 같은 변경)."""
    from sqlalchemy import inspect, text

    col = next((c for c in inspect(sync_conn).get_columns("token_usages") if c["name"] == "conversation_id"), None)
    if col is not None and not col["nullable"]:
        sync_conn.execute(text("ALTER TABLE token_usages MODIFY conversation_id VARCHAR(36) NULL"))

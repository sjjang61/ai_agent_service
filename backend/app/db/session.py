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
    from app.models import user, conversation, message, mcp_config, tool_execution, sandbox, skill, memory, scheduled_task  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

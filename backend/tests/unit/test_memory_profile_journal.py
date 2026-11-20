"""USER.md(프로필)와 Episodes(날짜별 일지): 저장·합치기·프롬프트 중복 제거·일지 기록 (메모리 SQLite)."""
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agent.orchestrator import _build_memory_context
from app.db.base import Base
from app.models.memory import Memory, MemoryJournal, UserProfile
from app.schemas.memory import EpisodeDetail, MemoryCreate
from app.services import memory_journal as mj
from app.services import memory_profile as mp
from app.services.memory_service import MemoryService

U = "user-1"


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[Memory.__table__, UserProfile.__table__, MemoryJournal.__table__]))
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


def test_clean_markdown_strips_code_fence_and_limits_length():
    assert mp.clean_markdown("```markdown\n## 배경\n- a\n```") == "## 배경\n- a"
    assert len(mp.clean_markdown("x" * 9000)) == mp.MAX_PROFILE_CHARS


@pytest.mark.asyncio
async def test_profile_save_and_covered_logic(db):
    old = await MemoryService.create_memory(U, MemoryCreate(key="job", value="백엔드 개발자", category="fact"), db)
    assert mp.is_covered(old, None) is False  # 문서가 없으면 아무것도 합쳐지지 않았다
    row = await mp.save_profile(U, "## 배경\n- 백엔드 개발자", merged=False, db=db)
    assert row.merged_at is None and mp.is_covered(old, row) is False  # 직접 쓴 문서는 메모리를 대신하지 않는다 (중복되더라도 빠뜨리지 않는다)
    row = await mp.save_profile(U, "## 배경\n- 백엔드 개발자", merged=True, db=db)
    assert row.merged_at is not None and mp.is_covered(old, row) is True
    new = Memory(user_id=U, key="lang", value="Go 선호", memory_type="semantic", created_at=row.merged_at + timedelta(seconds=5), updated_at=row.merged_at + timedelta(seconds=5))
    assert mp.is_covered(new, row) is False  # 합친 뒤에 저장된 것은 따로 전달된다


@pytest.mark.asyncio
async def test_prompt_memories_use_profile_and_skip_merged_items(db):
    await MemoryService.create_memory(U, MemoryCreate(key="job", value="백엔드 개발자", category="fact"), db)
    await MemoryService.create_memory(U, MemoryCreate(key="tone", value="존댓말로 답한다", category="instruction"), db)
    before = await MemoryService.get_prompt_memories(U, db, "")
    assert before["profile"] == "" and len(before["semantic"]) == 1 and len(before["procedural"]) == 1

    await mp.save_profile(U, "## 배경\n- 백엔드 개발자\n## 작업 방식\n- 존댓말로 답한다", merged=True, db=db)
    after = await MemoryService.get_prompt_memories(U, db, "")
    assert "백엔드 개발자" in after["profile"] and after["semantic"] == [] and after["procedural"] == []  # 문서로 전달되므로 목록에서는 빠진다
    ctx = _build_memory_context(after, {})
    assert "USER.md" in ctx and ctx.count("백엔드 개발자") == 1


@pytest.mark.asyncio
async def test_episodic_memory_is_logged_to_that_days_journal(db):
    when = datetime(2026, 11, 20, 5, 30)  # UTC → 기본 시간대(Asia/Seoul)로 14:30
    await MemoryService.create_memory(
        U,
        MemoryCreate(key="n1", value="N+1 쿼리 해결", category="general", memory_type="episodic", occurred_at=when,
                     detail=EpisodeDetail(situation="목록 API 느림", resolution="selectinload 적용", outcome="3배 빨라짐")),
        db,
    )
    row = await mj.get_day(U, "2026-11-20", db)
    assert row is not None and "14:30 N+1 쿼리 해결 — 목록 API 느림 → selectinload 적용 (3배 빨라짐)" in row.content
    await mj.append_line(U, "2026-11-20", row.content.splitlines()[0], db)  # 같은 줄은 중복으로 쌓지 않는다
    assert (await mj.get_day(U, "2026-11-20", db)).content.count("N+1 쿼리 해결") == 1
    # 사실 메모리는 일지에 남지 않는다
    await MemoryService.create_memory(U, MemoryCreate(key="job", value="개발자", category="fact"), db)
    assert len(await mj.list_days(U, db)) == 1


@pytest.mark.asyncio
async def test_journal_edit_delete_list_and_backfill(db):
    assert mj.valid_day("2026-11-20") and not mj.valid_day("2026-13-40") and not mj.valid_day("11-20")
    await mj.save_day(U, "2026-11-19", "- 직접 쓴 메모", db)
    await mj.save_day(U, "2026-11-21", "- 다른 날", db)
    assert [r.day for r in await mj.list_days(U, db)] == ["2026-11-21", "2026-11-19"]  # 최근 날짜부터
    assert [r.day for r in await mj.list_days(U, db, before="2026-11-21")] == ["2026-11-19"]
    assert await mj.save_day(U, "2026-11-19", "  ", db) is None  # 비우면 그날 일지를 지운다
    assert await mj.delete_day(U, "2026-11-21", db) is True and await mj.delete_day(U, "2026-11-21", db) is False


@pytest.mark.asyncio
async def test_backfill_moves_existing_episodes_once(db):
    db.add(Memory(user_id=U, key="old", value="옛 사례", memory_type="episodic", occurred_at=datetime(2026, 10, 1, 0, 0), detail={"situation": "A", "resolution": "B"}, importance=5))
    await db.commit()
    assert await mj.backfill(U, db) == 1
    assert (await mj.get_day(U, "2026-10-01", db)).content.endswith("옛 사례 — A → B")
    assert await mj.backfill(U, db) == 0  # 일지가 생긴 뒤에는 다시 옮기지 않는다

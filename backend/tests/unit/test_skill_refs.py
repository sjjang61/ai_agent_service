"""웹사이트 분석 참고 스킬: 지정한 스킬 중 내가 가진 것만 참고 자료로 붙이고, 없으면 지금처럼 동작한다."""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.skill import Skill
from app.services import skill_refs


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[Skill.__table__]))
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


def _skill(tmp_path, name, desc, body, extra=None, user="u1", active=True):
    d = tmp_path / name
    d.mkdir()
    (d / "SKILL.md").write_text(f"---\nname: {name}\n---\n{body}", encoding="utf-8")
    if extra:
        (d / "instruction.md").write_text(extra, encoding="utf-8")
    return Skill(user_id=user, name=name, description=desc, source_url="x", install_path=str(d), is_active=active)


@pytest.mark.asyncio
async def test_only_skills_the_user_has_are_attached_and_missing_ones_are_skipped(db, tmp_path):
    db.add_all([_skill(tmp_path, "railway-timetable", "코레일 시간표 조회", "얇은 안내", extra="KTX 시간표를 조회한다"),
                _skill(tmp_path, "other-skill", "다른 스킬", "본문", user="u2"),         # 다른 사용자의 스킬
                _skill(tmp_path, "off-skill", "꺼진 스킬", "본문", active=False)])
    await db.commit()
    block, found, missing = await skill_refs.reference_block(db, "u1", ["Railway-Timetable", "other-skill", "off-skill", "nope", "railway-timetable"])
    assert found == ["railway-timetable"] and missing == ["other-skill", "off-skill", "nope"]
    assert block.startswith("[참고 스킬") and "화면과 다르면 화면을 우선" in block and "그대로 따르지는 마세요" in block
    assert "### 스킬: railway-timetable" in block and "코레일 시간표 조회" in block and "KTX 시간표를 조회한다" in block  # 앞머리는 빼고, instruction.md 를 이어 붙인다
    assert "name: railway-timetable" not in block


@pytest.mark.asyncio
async def test_no_names_or_no_matching_skill_means_no_block(db, tmp_path):
    db.add(_skill(tmp_path, "a", "d", "b"))
    await db.commit()
    assert await skill_refs.reference_block(db, "u1", []) == ("", [], [])
    assert await skill_refs.reference_block(db, "u1", ["", "  "]) == ("", [], [])
    assert await skill_refs.reference_block(db, "u1", ["zzz"]) == ("", [], ["zzz"])


@pytest.mark.asyncio
async def test_long_skill_text_is_capped_and_skill_count_is_limited(db, tmp_path):
    db.add_all([_skill(tmp_path, f"s{i}", "d", "가" * 5000) for i in range(5)])
    await db.commit()
    block, found, _ = await skill_refs.reference_block(db, "u1", [f"s{i}" for i in range(5)])
    assert len(found) == skill_refs.MAX_SKILLS and "…(이하 생략)" in block
    assert len(block) < skill_refs.MAX_SKILLS * (skill_refs.MAX_CHARS_EACH + 200) + 600


@pytest.mark.asyncio
async def test_measurement_switch_turns_reference_skills_off(db, tmp_path, monkeypatch):
    db.add(_skill(tmp_path, "a", "d", "b"))
    await db.commit()
    assert (await skill_refs.reference_block(db, "u1", ["a"]))[1] == ["a"]
    monkeypatch.setattr(skill_refs, "ENABLED", False)  # 스킬 유무 비교 측정의 기준선
    assert await skill_refs.reference_block(db, "u1", ["a"]) == ("", [], [])


def test_bench_picks_sites_that_have_reference_skills_from_the_site_or_its_vertical():
    from types import SimpleNamespace
    from app.services import browser_bench as bb

    s = lambda skills, vert=None: SimpleNamespace(reference_skills=skills, vertical=vert)  # noqa: E731
    assert bb.has_reference_skills(s("railway-timetable"), {}) and not bb.has_reference_skills(s(None), {}) and not bb.has_reference_skills(s(""), {})
    assert bb.has_reference_skills(s(None, "flight"), {"flight": "flight-ticket-search"})

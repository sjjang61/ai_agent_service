"""웹사이트 분석: 분야·사이트 편집 서비스 (메모리 SQLite)."""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agent import site_tips
from app.db.base import Base
from app.models.site_profile import SiteAnalysisRun, SiteProfile, SiteProfileRevision, SiteVertical
from app.services import site_profile_service as svc
from app.services.site_profile_service import ProfileError


@pytest_asyncio.fixture
async def db():
    site_tips.clear_cache()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[SiteVertical.__table__, SiteProfile.__table__, SiteProfileRevision.__table__, SiteAnalysisRun.__table__]))
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as s:
        await svc.seed_from_files(s)
        await svc.refresh(s)
        yield s
    await engine.dispose()
    site_tips.clear_cache()


def site(**kw):
    return {"name": "테스트 항공", "vertical": "flight", "domains": "https://www.Air.TestFly.com/x", "aliases": "네이버항공권, 테스트 항공",
            "body": "검색은 주소로 이동하세요.", "status": "verified", "verified_at": "2026-11-18", "enabled": True, **kw}


def test_normalize_domains_and_csv():
    assert svc.normalize_domains("https://www.Danawa.com/x?y, search.danawa.com:443 danawa.com") == "danawa.com, search.danawa.com"
    for bad in ("localhost", "a b.c", "http://"):
        if bad.strip("http://"):
            with pytest.raises(ProfileError):
                svc.normalize_domains(bad)
    assert svc.normalize_csv("a, b,\n A ,,c") == "a, b, c"


@pytest.mark.asyncio
async def test_create_site_normalizes_updates_runtime_and_bumps_version(db):
    row = await svc.save_site(db, site())
    assert row.domains == "air.testfly.com" and row.source == "ui" and row.version == 1
    tip = site_tips.for_url("https://air.testfly.com/flights/")  # 저장하면 에이전트가 바로 쓴다
    assert tip.name == "테스트 항공" and tip.vertical == "flight"
    row = await svc.save_site(db, site(body="고친 요령"), site_id=row.id, version=1)
    assert row.version == 2 and site_tips.for_url("https://air.testfly.com").body == "고친 요령"
    with pytest.raises(ProfileError) as e:
        await svc.save_site(db, site(body="낡은 화면에서 저장"), site_id=row.id, version=1)  # 다른 사용자가 먼저 고쳤다
    assert e.value.status == 409


@pytest.mark.asyncio
async def test_validation_errors(db):
    await svc.save_site(db, site())
    cases = [
        (site(name=" "), 400), (site(name="x", domains=""), 400), (site(vertical="nope", name="x", domains="x.com"), 404),
        (site(status="weird", name="x", domains="x.com"), 400), (site(verified_at="11/18", name="x", domains="x.com"), 400),
        (site(), 409),  # 같은 이름
        (site(name="다른 이름"), 409),  # 같은 도메인
        (site(name="다나와2", domains="danawa.com", vertical="shopping"), 409),  # 시드된 다나와와 같은 분야에서 겹침
    ]
    for data, status in cases:
        with pytest.raises(ProfileError) as e:
            await svc.save_site(db, data)
        assert e.value.status == status, data


@pytest.mark.asyncio
async def test_draft_and_disabled_are_not_given_to_agent_and_verified_gets_date(db):
    row = await svc.save_site(db, site(status="draft", verified_at=None))
    assert site_tips.for_url("https://air.testfly.com") is None  # 초안은 주지 않는다
    row = await svc.save_site(db, site(status="verified", verified_at=None), site_id=row.id)
    assert row.verified_at and site_tips.for_url("https://air.testfly.com").name == "테스트 항공"  # 확인함으로 바꾸면 오늘 날짜가 찍힌다
    await svc.save_site(db, site(enabled=False), site_id=row.id)
    assert site_tips.for_url("https://air.testfly.com") is None


@pytest.mark.asyncio
async def test_stale_marking_does_not_stop_the_agent_from_using_it(db):
    from datetime import date

    row = await svc.save_site(db, site(verified_at="2026-01-01"))
    assert svc.is_stale(row, date(2026, 11, 19)) and not svc.is_stale(row, date(2026, 1, 20))
    assert site_tips.for_url("https://air.testfly.com") is not None


@pytest.mark.asyncio
async def test_vertical_create_update_delete_rules(db):
    with pytest.raises(ProfileError):
        await svc.save_vertical(db, {"key": "Bad Key", "name": "x", "body": "b"})
    with pytest.raises(ProfileError) as e:
        await svc.save_vertical(db, {"key": "flight", "name": "x", "body": "b"})  # 이미 있는 키
    assert e.value.status == 409
    v = await svc.save_vertical(db, {"key": "car_rental", "name": "렌터카", "keywords": "렌터카, 렌트카", "stop_words": "결제", "body": "지침", "checklist": "- 확인"})
    assert site_tips.vertical("car_rental").keywords == ("렌터카", "렌트카")
    v = await svc.save_vertical(db, {"key": "ignored", "name": "렌터카2", "body": "지침2"}, key="car_rental", version=1)
    assert v.key == "car_rental" and v.name == "렌터카2" and v.version == 2  # 키는 바뀌지 않는다
    await svc.save_site(db, site(vertical="car_rental"))
    with pytest.raises(ProfileError) as e:
        await svc.delete_vertical(db, "car_rental")  # 쓰는 사이트가 있으면 삭제할 수 없다
    assert e.value.status == 409
    await svc.delete_site(db, (await svc.list_all(db))[1][-1].id) if False else None
    sites = (await svc.list_all(db))[1]
    await svc.delete_site(db, next(s.id for s in sites if s.vertical == "car_rental"))
    await svc.delete_vertical(db, "car_rental")
    assert site_tips.vertical("car_rental") is None


@pytest.mark.asyncio
async def test_md_export_roundtrips_through_the_file_parser(db, tmp_path):
    row = await svc.save_site(db, site())
    p = tmp_path / "x.md"
    p.write_text(svc.site_md(row), encoding="utf-8")
    t = site_tips.parse_site_file(p)
    assert (t.name, t.domains, t.vertical, t.verified, t.body) == ("테스트 항공", ("air.testfly.com",), "flight", "2026-11-18", "검색은 주소로 이동하세요.")
    vert = (await svc.list_all(db))[0][0]
    p.write_text(svc.vertical_md(vert), encoding="utf-8")
    v = site_tips.parse_vertical_file(p)
    assert (v.key, v.body, v.checklist) == (vert.key, vert.body.strip(), vert.checklist.strip())


@pytest.mark.asyncio
async def test_preview_shows_vertical_then_site(db):
    verticals, _ = await svc.list_all(db)
    flight = next(v for v in verticals if v.key == "flight")
    text = svc.preview_text(SiteProfile(name="X", vertical="flight", domains="x.com", body="요령", verified_at="2026-11-18"), flight)
    assert text.index("[분야 지침 · 항공권]") < text.index("[사이트 요령 · X")


def test_routes_are_declared():
    from app.api import site_profiles

    paths = {(m, r.path) for r in site_profiles.router.routes for m in r.methods}
    assert {("GET", ""), ("POST", "/sites"), ("PUT", "/sites/{site_id}"), ("DELETE", "/sites/{site_id}"), ("POST", "/sites/preview"),
            ("POST", "/verticals"), ("PUT", "/verticals/{key}"), ("DELETE", "/verticals/{key}")} <= paths


# ── 수정 이력 ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_history_records_each_save_and_first_edit_keeps_the_seed_state(db):
    from sqlalchemy import select as sel

    dn = (await db.execute(sel(SiteProfile).where(SiteProfile.name == "다나와"))).scalar_one()
    original_body = dn.body
    assert await svc.list_revisions(db, "site", dn.id) == []  # 시드만 된 항목은 이력이 없다
    data = lambda body: {"name": "다나와", "vertical": "shopping", "domains": "danawa.com", "aliases": "다나와", "body": body, "status": "verified", "verified_at": "2026-11-18"}
    await svc.save_site(db, data("첫 수정"), site_id=dn.id, author="홍길동")
    await svc.save_site(db, data("두 번째 수정"), site_id=dn.id, author="김철수")
    revs = await svc.list_revisions(db, "site", dn.id)
    assert [r.version for r in revs] == [3, 2, 1]  # 최신이 먼저. 맨 아래가 고치기 전(시드) 상태다
    assert [r.snapshot["body"] for r in revs] == ["두 번째 수정", "첫 수정", original_body]
    assert [r.author for r in revs] == ["김철수", "홍길동", None] and revs[2].source == "seed"

    restored = await svc.restore_site(db, dn.id, revs[2].id, author="관리")  # 시드 상태로 되돌리기
    assert restored.body == original_body and restored.version == 4
    revs = await svc.list_revisions(db, "site", dn.id)
    assert revs[0].source == "restore" and revs[0].author == "관리" and len(revs) == 4  # 되돌린 것도 이력에 남는다
    assert site_tips.for_url("https://www.danawa.com").body == original_body  # 에이전트에게도 바로 반영
    with pytest.raises(ProfileError) as e:
        await svc.restore_site(db, dn.id, "nope")
    assert e.value.status == 404


@pytest.mark.asyncio
async def test_history_is_capped_and_removed_with_the_item(db, monkeypatch):
    monkeypatch.setattr(svc, "MAX_REVISIONS", 3)
    row = await svc.save_site(db, site())
    for i in range(5):
        row = await svc.save_site(db, site(body=f"v{i}"), site_id=row.id)
    revs = await svc.list_revisions(db, "site", row.id)
    assert [r.version for r in revs] == [6, 5, 4]  # 오래된 것부터 지운다
    await svc.delete_site(db, row.id)
    assert await svc.list_revisions(db, "site", row.id) == []


@pytest.mark.asyncio
async def test_vertical_history_and_restore(db):
    v = await svc.save_vertical(db, {"name": "항공권2", "keywords": "항공권", "body": "바뀐 지침"}, key="flight", author="a")
    revs = await svc.list_revisions(db, "vertical", "flight")
    assert [r.version for r in revs] == [2, 1] and revs[1].snapshot["name"] == "항공권"
    back = await svc.restore_vertical(db, "flight", revs[1].id)
    assert back.name == "항공권" and back.version == 3 and site_tips.vertical("flight").name == "항공권"


@pytest.mark.asyncio
async def test_same_domain_is_allowed_only_for_a_different_vertical(db):
    flight = await svc.save_site(db, site(name="아고다 항공", vertical="flight", domains="agoda-test.com"))
    hotel = await svc.save_site(db, site(name="아고다 호텔", vertical="hotel", domains="agoda-test.com"))  # 분야가 다르면 같은 도메인 가능
    assert flight.domains == hotel.domains
    with pytest.raises(ProfileError) as e:
        await svc.save_site(db, site(name="아고다 항공 2", vertical="flight", domains="agoda-test.com"))  # 같은 분야는 불가
    assert e.value.status == 409 and "같은 분야" in e.value.detail
    assert site_tips.for_url("https://agoda-test.com", {"hotel"}).name == "아고다 호텔"


@pytest.mark.asyncio
async def test_seed_renames_the_old_single_agoda_row_in_place(db):
    from sqlalchemy import select as sel

    rows = (await db.execute(sel(SiteProfile).where(SiteProfile.domains == "agoda.com"))).scalars().all()
    assert {r.name: r.vertical for r in rows} == {"아고다 · 항공권": "flight", "아고다 · 호텔": "hotel"}
    old = next(r for r in rows if r.vertical == "hotel")
    old.name = "아고다"  # 이전 버전이 시드한 행 (항공권 하나뿐이던 때)
    old.vertical = "flight"
    fl = next(r for r in rows if r.vertical == "flight" and r.name != "아고다")
    await db.delete(fl)
    await db.commit()
    await svc.seed_from_files(db)
    names = {r.name: r.vertical for r in (await db.execute(sel(SiteProfile).where(SiteProfile.domains == "agoda.com"))).scalars().all()}
    assert names == {"아고다 · 항공권": "flight", "아고다 · 호텔": "hotel"}  # 이름만 바뀌고(행 재사용), 없던 호텔 행이 추가된다

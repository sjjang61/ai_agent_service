"""웹사이트 분석 구조화(spec): 검증·정리, 에이전트용 텍스트, md 왕복, 서비스 저장."""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agent import site_spec, site_tips
from app.db.base import Base
from app.models.site_profile import SiteAnalysisRun, SiteProfile, SiteProfileRevision, SiteVertical
from app.services import site_profile_service as svc
from app.services.site_profile_service import ProfileError

VSPEC = {"inputs": [{"key": "origin", "label": "출발지", "required": True, "example": "서울"}, {"key": "date", "label": "날짜"}],
         "flow": [{"key": "search", "title": "검색"}, {"key": "book", "title": "담기", "write": True}], "sample": {"origin": "서울", "zzz": "버림"}}


def test_clean_vertical_drops_blank_rows_and_unknown_samples():
    out = site_spec.clean_vertical({**VSPEC, "inputs": VSPEC["inputs"] + [{"key": "", "label": ""}]})
    assert [i["key"] for i in out["inputs"]] == ["origin", "date"] and out["inputs"][1]["required"] is True
    assert out["sample"] == {"origin": "서울"}  # 정의되지 않은 입력값의 샘플은 버린다
    assert out["flow"][1]["write"] is True
    assert site_spec.clean_vertical({}) == {} and site_spec.clean_vertical({"inputs": [], "flow": []}) == {}


@pytest.mark.parametrize("bad", [
    {"inputs": [{"key": "Bad Key", "label": "x"}]}, {"inputs": [{"key": "a"}, {"key": "a"}]},
    {"flow": [{"key": "1x", "title": "t"}]}, {"inputs": "nope"}, {"inputs": [{"key": f"k{i}"} for i in range(21)]},
])
def test_clean_vertical_rejects_bad_input(bad):
    with pytest.raises(site_spec.SpecError):
        site_spec.clean_vertical(bad)


def test_clean_site_validates_urls_and_keys():
    out = site_spec.clean_site({"entry": [{"label": "검색", "url": "https://a.com/s?q={query}"}, {"label": "빈 행", "url": ""}],
                                "menus": [{"name": "항공권", "path": "상단 > 항공권", "url": ""}, {"name": ""}],
                                "inputs": {"origin": {"how": "자동완성에서 고른다", "param": ""}, "date": {"how": "", "param": ""}},
                                "flow": [{"key": "search", "how": "주소로 이동"}, {"key": "x", "how": "", "url": ""}], "stop_point": "예약자 정보 화면"})
    assert len(out["entry"]) == 1 and len(out["menus"]) == 1 and list(out["inputs"]) == ["origin"] and len(out["flow"]) == 1
    for bad in ({"entry": [{"url": "javascript:alert(1)"}]}, {"menus": [{"name": "a", "url": "ftp://x"}]}, {"inputs": {"Bad Key": {"how": "x"}}},
                {"flow": [{"key": "a", "how": "x"}, {"key": "a", "how": "y"}]}):
        with pytest.raises(site_spec.SpecError):
            site_spec.clean_site(bad)
    assert site_spec.clean_site({"entry": [], "stop_point": " "}) == {}


def test_render_uses_vertical_labels_and_order():
    vs = site_spec.clean_vertical(VSPEC)
    text = site_spec.render_vertical(vs)
    assert "출발지 (origin, 필수) — 예: 서울" in text and "날짜 (date, 필수)" in text and "[상태를 바꾸는 단계" in text
    ss = site_spec.clean_site({"flow": [{"key": "book", "how": "담기 버튼"}, {"key": "search", "how": "주소 이동"}], "inputs": {"origin": {"how": "자동완성", "param": "from"}},
                               "entry": [{"label": "검색", "url": "https://a.com/?f={origin}"}], "menus": [{"name": "항공권", "path": "GNB", "url": ""}], "stop_point": "결제창"})
    out = site_spec.render_site(ss, vs)
    assert out.index("1. 검색: 주소 이동") < out.index("2. 담기: 담기 버튼")  # 분야 단계 순서대로
    assert "출발지: 자동완성 [주소 파라미터: from]" in out and "멈출 지점: 결제창" in out and "항공권 — GNB" in out
    assert site_spec.render_vertical({}) == "" and site_spec.render_site({}, vs) == ""


def test_sample_text_prefers_overrides_and_skips_unknown():
    vs = site_spec.clean_vertical(VSPEC)
    assert site_spec.sample_text(vs) == "- 출발지 (origin): 서울"
    assert site_spec.sample_text(vs, {"origin": "부산", "date": "내일", "zzz": "x"}) == "- 출발지 (origin): 부산\n- 날짜 (date): 내일"
    assert site_spec.sample_text(None) == ""


def test_seed_files_have_structure_for_all_verticals_and_block_includes_it():
    for v in site_tips.file_verticals():
        assert v.spec["inputs"] and v.spec["flow"] and v.spec["sample"], v.key
        assert any(not s["write"] for s in v.spec["flow"]) and v.spec["flow"][-1]["key"] == "stop", v.key  # 마지막은 멈춤 단계
        keys = {i["key"] for i in v.spec["inputs"]}
        assert set(v.spec["sample"]) <= keys
        assert "입력값" in v.block() and "표준 진행 단계" in v.block()
    dn = next(t for t in site_tips.file_tips() if t.name == "다나와")
    assert "{query}" in dn.block() and "진입·직접 이동 주소" in dn.block()


def test_split_spec_roundtrip_and_errors(tmp_path):
    p = tmp_path / "x.md"
    p.write_text('---\nname: X\ndomains: x.com\nverified: 2026-11-01\n---\n```spec\n{"entry": [{"label": "a", "url": "https://x.com/{q}"}]}\n```\n\n본문\n', encoding="utf-8")
    t = site_tips.parse_site_file(p)
    assert t.body == "본문" and t.spec["entry"][0]["url"] == "https://x.com/{q}"
    p.write_text('---\nname: X\ndomains: x.com\nverified: 2026-11-01\n---\n```spec\n{not json}\n```\n본문\n', encoding="utf-8")
    with pytest.raises(ValueError, match="x.md"):
        site_tips.parse_site_file(p)


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


SITE = {"name": "테스트 항공", "vertical": "flight", "domains": "air.testfly.com", "body": "예외", "status": "verified", "verified_at": "2026-11-18"}


@pytest.mark.asyncio
async def test_seed_carries_structure_and_fills_old_seed_rows(db):
    from sqlalchemy import select

    fl = (await db.execute(select(SiteVertical).where(SiteVertical.key == "flight"))).scalar_one()
    assert fl.spec["inputs"][0]["key"] == "trip_type"
    fl.spec = None  # 구조화 이전에 시드된 행
    await db.commit()
    await svc.seed_from_files(db)
    await db.refresh(fl)
    assert fl.spec and fl.version == 1
    fl.source, fl.spec = "ui", None  # 화면에서 고친 행(구조를 일부러 비운 것일 수 있다)은 건드리지 않는다
    await db.commit()
    await svc.seed_from_files(db)
    await db.refresh(fl)
    assert not fl.spec


@pytest.mark.asyncio
async def test_save_site_spec_is_cleaned_kept_when_omitted_and_reaches_the_agent(db):
    row = await svc.save_site(db, {**SITE, "spec": {"entry": [{"label": "검색", "url": "https://air.testfly.com/?o={origin}"}], "inputs": {"origin": {"how": "자동완성"}}}})
    assert row.spec["inputs"]["origin"] == {"how": "자동완성", "param": ""}
    tip = site_tips.for_url("https://air.testfly.com")
    assert "https://air.testfly.com/?o={origin}" in tip.block() and "출발지: 자동완성" in tip.block()  # 분야의 라벨로 풀린다
    row = await svc.save_site(db, {k: v for k, v in SITE.items()}, site_id=row.id)  # spec 을 보내지 않으면 유지
    assert row.spec["entry"]
    row = await svc.save_site(db, {**SITE, "spec": {}}, site_id=row.id)  # 빈 spec 은 비운다
    assert row.spec is None
    with pytest.raises(ProfileError) as e:
        await svc.save_site(db, {**SITE, "spec": {"entry": [{"url": "javascript:x"}]}}, site_id=row.id)
    assert e.value.status == 400


@pytest.mark.asyncio
async def test_vertical_spec_history_restore_and_md_export(db, tmp_path):
    v = await svc.save_vertical(db, {"name": "항공권", "body": "지침", "spec": {"inputs": [{"key": "origin", "label": "출발"}], "flow": []}}, key="flight")
    assert v.spec["inputs"][0]["label"] == "출발" and v.version == 2
    revs = await svc.list_revisions(db, "vertical", "flight")
    assert revs[1].snapshot["spec"]["inputs"][0]["key"] == "trip_type"  # 고치기 전 구조가 이력에 남는다
    p = tmp_path / "f.md"
    p.write_text(svc.vertical_md(v), encoding="utf-8")
    back = site_tips.parse_vertical_file(p)
    assert back.spec == v.spec and back.body == "지침"
    back = await svc.restore_vertical(db, "flight", revs[1].id)
    assert back.spec["inputs"][0]["key"] == "trip_type"
    row = await svc.save_site(db, {**SITE, "spec": {"stop_point": "x"}})
    p.write_text(svc.site_md(row), encoding="utf-8")
    assert site_tips.parse_site_file(p).spec == {"entry": [], "menus": [], "inputs": {}, "flow": [], "stop_point": "x"}


@pytest.mark.asyncio
async def test_preview_uses_the_unsaved_vertical_for_labels(db):
    verticals, _ = await svc.list_all(db)
    flight = next(v for v in verticals if v.key == "flight")
    site = SiteProfile(name="X", vertical="flight", domains="x.com", body="", verified_at="2026-11-18", spec={"inputs": {"origin": {"how": "h", "param": ""}}})
    assert "출발지: h" in svc.preview_text(site, flight)


@pytest.mark.asyncio
async def test_draft_seed_sites_are_listed_for_analysis_but_not_given_to_the_agent(db):
    from sqlalchemy import select

    rows = {r.name: r for r in (await db.execute(select(SiteProfile))).scalars().all()}
    for name, vert in (("스카이스캐너", "flight"), ("네이버 항공권", "flight"), ("아고다 · 항공권", "flight"), ("아고다 · 호텔", "hotel")):
        assert rows[name].status == "draft" and rows[name].vertical == vert and rows[name].verified_at is None
    assert site_tips.for_url("https://www.skyscanner.co.kr/transport/flights/") is None  # 분석을 마쳐 검증됨으로 저장하기 전까지는 주지 않는다
    assert site_tips.for_url("https://flight.naver.com") is None or site_tips.for_url("https://flight.naver.com").name != "네이버 항공권"

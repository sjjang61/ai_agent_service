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
    for t in site_tips.file_tips():  # md 시드의 상태(verified/draft)가 DB 로 그대로 들어간다. 초안은 시드돼도 검증됨으로 바뀌지 않는다
        assert rows[t.name].status == t.status and (rows[t.name].vertical or "") == t.vertical, t.name  # 분야가 없는 사이트는 DB 에서 None, md 에서는 ''
        if t.status == "draft":
            assert rows[t.name].verified_at is None
            assert t.name not in {x.name for d in t.domains for x in site_tips.tips_for_url(f"https://www.{d}/")}  # 분석을 마쳐 검증됨으로 저장하기 전까지는 주지 않는다
    assert any(t.status == "draft" for t in site_tips.file_tips())  # (초안이 하나도 없으면 이 테스트가 아무것도 확인하지 못한다)


def test_mail_and_restaurant_verticals_keep_reads_separate_from_state_changes():
    mail, rest = site_tips.vertical("mail"), site_tips.vertical("restaurant")
    # 메일: 발송·삭제 등은 쓰기 단계(분석·검증에서 시험하지 않는다), 영구 삭제는 항상 막는다, 메일 본문은 신뢰할 수 없는 데이터로 다룬다
    assert [s["key"] for s in mail.spec["flow"] if s["write"]] == ["act"] and "영구 삭제" in mail.stop_words
    assert "신뢰할 수 없는 데이터" in mail.body and "개인정보" in mail.checklist  # 분석 중 메일 내용을 기록하지 않는다
    # 식당 예약: 예약자 정보 입력은 쓰기 단계, 예약 확정·예약금 결제는 막는다
    assert [s["key"] for s in rest.spec["flow"] if s["write"]] == ["form"] and {"예약 확정", "예약금 결제"} <= set(rest.stop_words)
    # 키워드는 서로, 그리고 다른 분야와 겹치지 않는다 (겹치면 한 작업에 엉뚱한 분야 지침이 붙는다)
    owners: dict = {}
    for v in site_tips.file_verticals():
        for k in v.keywords:
            assert k not in owners, f"키워드 겹침: {k} ({owners[k]} / {v.key})"
            owners[k] = v.key
    assert {t.name for t in site_tips.file_tips() if t.vertical == "mail"} == {"네이버 메일", "다음 메일", "Gmail"}
    assert {t.name for t in site_tips.file_tips() if t.vertical == "restaurant"} == {"네이버 예약", "캐치테이블"}
    # 작업 문장으로 분야가 골라진다
    assert [v.key for v in site_tips.match_verticals("받은편지함에서 안 읽은 메일 확인해줘")] == ["mail"]
    assert [v.key for v in site_tips.match_verticals("강남 식당 예약 가능한 시간 알려줘")] == ["restaurant"]


def test_naver_shopping_seed_uses_the_working_search_path_and_skips_the_captcha_step():
    """네이버 쇼핑의 기존 경로(/search/all)는 접속 제한 화면이 나오고, 상품 링크의 판매처 스토어에는 보안 확인이 뜬다 (분석·검증으로 확인)."""
    t = next(x for x in site_tips.file_tips() if x.name == "네이버 가격비교")
    assert t.vertical == "shopping" and t.domains == ("shopping.naver.com",)
    assert t.spec["entry"][0]["url"] == "https://search.shopping.naver.com/ns/search?query={query}"  # 막히는 /search/all 이 아니다
    assert "/search/all" not in t.spec["entry"][0]["url"] and "/search/all" not in " ".join(f.get("url", "") for f in t.spec["flow"])
    detail = next(f for f in t.spec["flow"] if f["key"] == "detail")
    assert detail.get("skip") is True and "CAPTCHA" in detail["how"]  # 상세는 하지 않는 단계: 에이전트가 CAPTCHA 에 부딪히지 않게 한다
    movies = {x.name for x in site_tips.file_tips() if x.vertical == "movie"}
    assert movies == {"CGV", "메가박스", "롯데시네마"}


# ── 사이트 비활성화(사용 안 함): 에이전트가 그 사이트에 접속하지 않는다 ───────────────
def _states(*rows):
    site_tips.set_cache([], [], [site_tips.SiteState(name=n, domains=tuple(d.split(", ")), aliases=tuple(a.split(", ")) if a else (), enabled=e) for n, d, a, e in rows])


def test_disabled_site_is_blocked_only_when_every_row_for_the_domain_is_off():
    try:
        _states(("지마켓", "gmarket.co.kr", "지마켓, g마켓", False), ("다나와", "danawa.com", "다나와", True),
                ("아고다 · 항공권", "agoda.com", "아고다", False), ("아고다 · 호텔", "agoda.com", "아고다", True),
                ("검색엔진", "naver.com", "", False), ("네이버 항공권", "flight.naver.com", "", True))
        msg = site_tips.blocked("https://www.gmarket.co.kr/n/search?keyword=a")
        assert msg and "지마켓" in msg and "사용 안 함" in msg and "다시 열지 말고" in msg
        assert site_tips.blocked("https://search.danawa.com/") is None  # 켜진 사이트
        assert site_tips.blocked("https://www.agoda.com/flights") is None  # 같은 도메인의 호텔 행이 켜져 있으면 막지 않는다
        assert site_tips.blocked("https://mail.naver.com/") is not None  # 더 넓은 naver.com 행이 꺼져 있고
        assert site_tips.blocked("https://flight.naver.com/") is None  # 더 구체적인 도메인의 켜진 행이 이긴다
        assert site_tips.blocked("https://example.com/") is None
    finally:
        site_tips.clear_cache()
    assert site_tips.blocked("https://www.gmarket.co.kr/") is None  # 캐시가 없으면(파일 기본값) 막지 않는다


def test_start_blocks_warns_about_a_disabled_site_the_task_names():
    try:
        _states(("지마켓", "gmarket.co.kr", "지마켓, g마켓", False), ("다나와", "danawa.com", "다나와", True))
        blocks, _ = site_tips.start_blocks("지마켓에서 진라면 최저가 찾아줘")
        assert blocks and blocks[0].startswith("[사용 안 함 사이트] 지마켓") and "건너뛰고" in blocks[0]
        assert not any("[사용 안 함" in b for b in site_tips.start_blocks("다나와에서 진라면 최저가")[0])  # 켜진 사이트나 언급 없는 작업은 안내하지 않는다
        assert site_tips.disabled_blocks("https://www.gmarket.co.kr/ 열어줘")  # 주소로 가리켜도
    finally:
        site_tips.clear_cache()


@pytest.mark.asyncio
async def test_turning_a_site_off_in_settings_blocks_it_and_turning_it_on_restores(db):
    row = await svc.save_site(db, {**SITE, "name": "꺼 볼 사이트", "domains": "offtest.example.com", "vertical": "flight"})
    assert site_tips.blocked("https://offtest.example.com/x") is None
    await svc.save_site(db, {"name": row.name, "vertical": "flight", "domains": row.domains, "aliases": "", "body": row.body, "status": "verified", "enabled": False}, site_id=row.id)
    assert "꺼 볼 사이트" in site_tips.blocked("https://offtest.example.com/x")  # 저장 즉시 반영
    await svc.save_site(db, {"name": row.name, "vertical": "flight", "domains": row.domains, "aliases": "", "body": row.body, "status": "verified", "enabled": True}, site_id=row.id)
    assert site_tips.blocked("https://offtest.example.com/x") is None


# ── '이 사이트에서는 하지 않는 단계' (skip) ───────────────────────────────────
def test_site_flow_can_mark_a_step_as_not_done_on_this_site():
    vs = site_spec.clean_vertical(VSPEC)
    out = site_spec.clean_site({"flow": [{"key": "search", "how": "주소로 이동"}, {"key": "book", "how": "보안 확인(CAPTCHA)이 떠서 하지 않는다. 목록 정보로 답한다.", "skip": True},
                                         {"key": "x", "how": "", "url": "", "skip": False}]})
    assert out["flow"] == [{"key": "search", "how": "주소로 이동", "url": ""}, {"key": "book", "how": "보안 확인(CAPTCHA)이 떠서 하지 않는다. 목록 정보로 답한다.", "url": "", "skip": True}]  # skip 표시는 있을 때만 키가 생긴다
    assert site_spec.skipped_keys(out) == {"book"} and site_spec.skipped_keys({}) == set()
    assert site_spec.clean_site({"flow": [{"key": "book", "skip": True}]})["flow"] == [{"key": "book", "how": "", "url": "", "skip": True}]  # 사유 없이 표시만 해도 남는다
    text = site_spec.render_site(out, vs)
    assert "1. 검색: 주소로 이동" in text and "2. 담기: [이 사이트에서는 하지 않는 단계] 보안 확인(CAPTCHA)이 떠서 하지 않는다." in text  # 에이전트에게 그대로 전달된다


def test_verification_does_not_penalize_a_step_the_site_marks_as_not_done():
    from app.services import site_analysis_service as sa

    vflow = [{"key": "search", "title": "검색"}, {"key": "detail", "title": "상세"}, {"key": "cart", "title": "담기", "write": True}]
    ok = {"success": True, "summary": "s", "issues": [], "steps": [{"key": "search", "status": "reached", "note": ""}, {"key": "detail", "status": "skipped", "note": "CAPTCHA"}]}
    assert not sa.evaluate(ok, [{"action": "goto"}], 0, 1, vflow)["passed"]  # 설명서가 제외하지 않으면 건너뛴 단계는 감점
    r = sa.evaluate(ok, [{"action": "goto"}], 0, 1, vflow, {"detail"})
    assert r["passed"] and [f["status"] for f in r["flow"]] == ["reached", "excluded", "untested"] and r["flow"][1]["note"] == "CAPTCHA"
    missing = {"success": True, "summary": "s", "issues": [], "steps": [{"key": "search", "status": "reached", "note": ""}]}  # 보고가 아예 없어도 제외된 단계는 감점하지 않는다
    assert sa.evaluate(missing, [{"action": "goto"}], 0, 1, vflow, {"detail"})["passed"]
    done = {"success": True, "summary": "s", "issues": [], "steps": [{"key": "search", "status": "reached", "note": ""}, {"key": "detail", "status": "reached", "note": "열림"}]}
    assert sa.evaluate(done, [{"action": "goto"}], 0, 1, vflow, {"detail"})["flow"][1]["status"] == "reached"  # 되는 날에는 도달한 것으로 인정한다
    assert not sa.evaluate({**ok, "steps": [{"key": "search", "status": "failed", "note": ""}]}, [{"action": "goto"}], 0, 1, vflow, {"detail"})["passed"]  # 다른 단계가 막히면 여전히 미통과


def test_transport_vertical_stops_before_payment_and_korail_is_verified_for_the_local_browser():
    v = site_tips.vertical("transport")
    assert [s["key"] for s in v.spec["flow"] if s["write"]] == ["select"] and {"결제하기", "예매 확정"} <= set(v.stop_words)
    assert [v.key for v in site_tips.match_verticals("서울에서 부산 가는 KTX 기차표 조회해줘")] == ["transport"]
    t = next(x for x in site_tips.file_tips() if x.name == "코레일")
    assert t.vertical == "transport" and t.status == "verified" and "korail.com" in t.domains and "railway-timetable" in t.body  # 로컬 브라우저에서 검증, sandbox 는 자동화 제한이 있어 본문에 안내


def test_every_vertical_and_vertical_less_site_has_a_known_category():
    """카테고리(쇼핑·교통·부동산·금융 …) > 분야(상세) > 사이트. 시드의 모든 분야는 카테고리가 있고, 분야 없는 사이트(검색엔진)는 자기 카테고리를 갖는다."""
    from app.agent import site_categories as sc

    assert {"shopping", "transport", "realestate", "finance", "search"} <= set(sc.KEYS)
    assert [v.key for v in site_tips.file_verticals() if v.category not in sc.NAMES] == []
    by = {v.key: v.category for v in site_tips.file_verticals()}
    assert by["flight"] == by["transport"] == "transport" and by["shopping"] == "shopping" and by["hotel"] == "travel"
    loose = [t for t in site_tips.file_tips() if not t.vertical]
    assert [(t.name, t.category) for t in loose] == [("검색엔진(구글·네이버·다음)", "search")]
    with pytest.raises(ValueError):
        sc.normalize("nope")
    assert sc.normalize("") == "" and sc.normalize(" Finance ") == "finance"


@pytest.mark.asyncio
async def test_category_is_saved_seeded_and_kept_when_a_client_does_not_send_it(db):
    from sqlalchemy import select
    from app.models.site_profile import SiteProfile, SiteVertical
    from app.services import site_profile_service as svc

    await svc.seed_from_files(db)
    assert (await db.execute(select(SiteVertical.category).where(SiteVertical.key == "flight"))).scalar_one() == "transport"
    se = (await db.execute(select(SiteProfile).where(SiteProfile.name == "검색엔진(구글·네이버·다음)"))).scalar_one()
    assert se.vertical is None and se.category == "search"
    # 카테고리를 보내지 않는 저장(이전 화면)은 값을 지우지 않는다. 빈 문자열은 비운다. 모르는 값은 거절한다
    base = {"name": se.name, "domains": se.domains, "body": se.body, "status": "verified"}
    assert (await svc.save_site(db, base, site_id=se.id)).category == "search"
    assert (await svc.save_site(db, {**base, "category": "finance"}, site_id=se.id)).category == "finance"
    assert (await svc.save_site(db, {**base, "category": ""}, site_id=se.id)).category is None
    with pytest.raises(svc.ProfileError):
        await svc.save_site(db, {**base, "category": "nope"}, site_id=se.id)
    # 분야가 있는 사이트는 자기 카테고리를 저장하지 않는다 (분야를 따른다)
    sky = (await db.execute(select(SiteProfile).where(SiteProfile.name == "스카이스캐너"))).scalar_one()
    out = await svc.save_site(db, {"name": sky.name, "vertical": sky.vertical, "domains": sky.domains, "body": sky.body, "status": sky.status, "category": "finance"}, site_id=sky.id)
    assert out.category is None

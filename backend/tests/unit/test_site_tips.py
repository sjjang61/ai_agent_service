"""사이트별 요령 리소스: 파일 형식, 매칭, 이동 시 한 번만 주입."""
import re
from datetime import date

import pytest

from app.agent import prompts, site_tips
from app.tools import browser_tools as bt


def test_every_tip_file_is_well_formed_and_domains_are_unique():
    tips = site_tips.file_tips()
    assert len(tips) >= 4
    seen: dict = {}
    for t in tips:
        assert t.name and t.domains, t
        if t.status == "verified":
            assert t.body or t.spec, t  # 에이전트에게 주는 요령은 구조화(spec)나 본문 중 하나는 있어야 한다 (draft 는 분석 전 자리)
        assert t.status in ("verified", "draft"), t
        if t.status == "verified":
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", t.verified) and date.fromisoformat(t.verified), f"{t.name}: verified 날짜 형식"
        for d in t.domains:
            key = (d, t.vertical)  # 같은 도메인은 분야가 다를 때만 겹칠 수 있다 (아고다 · 항공권 / 아고다 · 호텔)
            assert key not in seen, f"도메인 중복: {d} ({seen[key]} / {t.name})"
            seen[key] = t.name
        # 본문에도 주소 템플릿의 {입력키} 자리표시자가 있을 수 있다 (구조화 spec 과 같은 표기). 에이전트 지침에는 그대로 전달된다.


def test_prompt_no_longer_embeds_site_specific_facts():
    text = "\n".join(prompts.sections("browser_agent"))
    for marker in ("danawa", "priceASC", "gmarket", "enuri"):
        assert marker not in text  # 사이트 사실은 site_tips/ 로 옮겼다
    assert "사이트 요령" in text  # 프롬프트에는 '주어지면 따른다'는 규칙만 남는다


def test_match_by_url_text_and_alias():
    names = lambda task, url=None: {t.name for t in site_tips.match_task(task, url)}
    assert names("가격 확인", "https://search.danawa.com/dsearch.php?query=a") == {"다나와"}  # 하위 도메인
    assert names("지마켓과 에누리에서 최저가") == {"지마켓", "에누리"}  # 사이트 이름
    assert "다나와" in names("https://www.danawa.com 에서 검색")  # 작업 문장 속 주소
    assert names("다음 단계로 진행") == set()  # 흔한 단어('다음')는 이름으로 보지 않는다
    assert names("example.com 확인", "https://example.com") == set()
    assert site_tips.for_url("https://m.gmarket.co.kr/x").name == "지마켓" and site_tips.for_url("https://example.com") is None
    assert site_tips.for_url("not a url") is None


def test_tip_block_marks_screen_priority_only_for_just_in_time_hint():
    t = site_tips.for_url("https://www.danawa.com")
    assert "[사이트 요령 · 다나와 · 확인 2026-" in t.block() and "화면을 우선" in t.block()
    assert "화면을 우선" not in t.block(hint=False) and "sort=priceASC" in t.block()


def test_just_in_time_tip_is_appended_once_per_site():
    tool = bt.BrowserActionTool(user_id="u1")
    out = "URL: https://search.danawa.com/x\nTitle: T"
    tool.last_url = "https://search.danawa.com/x"
    first = tool._with_site_tip(out)
    assert first.startswith(out) and "[사이트 요령 · 다나와" in first
    assert tool._with_site_tip(out) == out  # 두 번째 방문부터는 붙이지 않는다
    tool.last_url = "https://example.com/"
    assert tool._with_site_tip(out) == out  # 요령이 없는 사이트
    tool.last_url = "https://www.gmarket.co.kr/"
    assert "[사이트 요령 · 지마켓" in tool._with_site_tip(out)
    tool.last_url = "https://www.enuri.com/"
    assert tool._with_site_tip("Error: 이동 실패") == "Error: 이동 실패"  # 오류 결과에는 붙이지 않는다
    # 시작할 때 이미 지침에 넣은 사이트는 다시 붙이지 않는다
    pre = bt.BrowserActionTool(user_id="u1", tips_shown={"에누리"})
    pre.last_url = "https://www.enuri.com/"
    assert pre._with_site_tip(out) == out
    # 도구 인스턴스마다 안내 이력이 따로다 (병렬 실행끼리 공유하지 않는다)
    assert bt.BrowserActionTool(user_id="u2").tips_shown == set()


@pytest.mark.asyncio
async def test_start_instructions_include_only_matching_site_tips(monkeypatch):
    captured = {}

    class FakeAgent:
        def __init__(self, **kw):
            captured.update(kw)

        async def arun(self, prompt):
            class R:
                content = "완료"

            return R()

    import agno.agent as agno_agent

    monkeypatch.setattr(agno_agent, "Agent", FakeAgent)
    monkeypatch.setattr("app.agent.agno_engine.build_agno_model", lambda *a, **k: object())

    async def noop(*a, **k):
        return None

    monkeypatch.setattr(bt, "persist_profile", noop)
    tool = bt.CliBrowserAgentTool(user_id="u1", login_enabled=False)
    out = await tool._arun_inner("다나와에서 진라면 검색", "https://www.danawa.com")
    assert "완료" in out
    ins = captured["instructions"]
    assert any("[사이트 요령 · 다나와" in i for i in ins) and not any("지마켓" in i and "[사이트 요령" in i for i in ins)
    assert not any("화면을 우선하세요.)" in i for i in ins)  # 시작 지침에는 '화면 우선' 꼬리말을 중복해서 붙이지 않는다
    assert ins[: len(bt.BROWSER_INSTRUCTIONS)] == bt.BROWSER_INSTRUCTIONS


# ── 분야(vertical) 공통 지침 ─────────────────────────────────
def test_every_vertical_file_is_well_formed_and_sites_reference_existing_verticals():
    verts = site_tips.file_verticals()
    assert {v.key for v in verts} >= {"shopping", "movie", "flight", "hotel"}
    assert len({v.key for v in verts}) == len(verts)
    for v in verts:
        assert v.key == v.key.lower() and v.name and v.keywords and v.body and v.checklist, v.key
        assert any(w in v.body for w in ("결제", "발송")), f"{v.key}: 결제(메일은 발송) 직전에 멈춘다는 지침이 있어야 한다"
        assert site_tips.CHECKLIST_HEADING not in v.body  # 체크리스트는 에이전트 지침에 섞이지 않는다
    for t in site_tips.file_tips():
        assert not t.vertical or t.vertical in {v.key for v in verts}, f"{t.name}: 없는 분야 {t.vertical}"


def test_vertical_block_goes_with_site_block_and_keywords_match_without_site():
    blocks, shown = site_tips.start_blocks("다나와에서 진라면 최저가", None)
    assert blocks[0].startswith("[전체 공통 지침]")  # 전체 공통 지침이 분야·사이트 지침보다 앞에 붙는다
    blocks = blocks[1:]
    assert blocks[0].startswith("[분야 지침 · 쇼핑") and "요령이 있는 사이트: " in blocks[0] and "다나와" in blocks[0]
    assert any(b.startswith("[사이트 요령 · 다나와") for b in blocks[1:]) and shown == {"다나와", "@shopping"}
    blocks, shown = site_tips.start_blocks("제주 항공권 최저가 알려줘", None)  # 사이트가 없어도 키워드로 분야 지침이 붙는다
    assert [b.split("\n")[0] for b in blocks if b.startswith("[분야")] == ["[분야 지침 · 항공권]", "[분야 지침 · 쇼핑 (가격비교)]"]
    assert "@flight" in shown
    blocks, shown = site_tips.start_blocks("영화 추천해줘", None)  # 흔한 단어만으로는 분야·사이트 지침이 붙지 않는다 (전체 공통 지침만)
    assert [b.split("\n")[0] for b in blocks] == ["[전체 공통 지침]"] and shown == set()


def test_jit_text_adds_vertical_once_then_only_new_sites():
    shown: set = set()
    first = site_tips.jit_text("https://www.danawa.com/", shown)
    assert first.startswith("[분야 지침 · 쇼핑") and "[사이트 요령 · 다나와" in first
    second = site_tips.jit_text("https://www.gmarket.co.kr/", shown)  # 같은 분야의 다른 사이트: 분야 지침은 다시 붙이지 않는다
    assert second.startswith("[사이트 요령 · 지마켓") and "[분야 지침" not in second
    assert site_tips.jit_text("https://www.danawa.com/", shown) == ""
    assert site_tips.jit_text("https://example.com/", shown) == ""


def test_stop_rules_come_from_active_verticals():
    words, urls = site_tips.stop_rules("https://www.danawa.com/", set())
    assert "구매하기" in words and urls == ()
    words, _ = site_tips.stop_rules("https://example.com/", {"@hotel"})
    assert "예약 확정" in words and "구매하기" not in words
    assert site_tips.stop_rules("https://example.com/", set()) == ((), ())


# ── DB 시드·로딩 ─────────────────────────────────────────────
@pytest.fixture
def clean_cache():
    site_tips.clear_cache()
    yield
    site_tips.clear_cache()


@pytest.mark.asyncio
async def test_seed_fills_missing_only_and_refresh_serves_db_content(clean_cache):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.db.base import Base
    from app.models.site_profile import SiteProfile, SiteProfileRevision, SiteVertical, SiteCommon
    from app.services import site_profile_service as svc

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[SiteVertical.__table__, SiteProfile.__table__, SiteProfileRevision.__table__, SiteCommon.__table__]))
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as db:
        added = await svc.seed_from_files(db)
        assert added == {"verticals": len(site_tips.file_verticals()), "sites": len(site_tips.file_tips())}
        assert await svc.seed_from_files(db) == {"verticals": 0, "sites": 0}  # 다시 해도 중복되지 않는다

        row = (await db.execute(select(SiteProfile).where(SiteProfile.name == "다나와"))).scalar_one()
        row.body = "DB 에서 고친 요령"
        await db.commit()
        assert await svc.seed_from_files(db) == {"verticals": 0, "sites": 0}  # 고친 내용은 덮어쓰지 않는다
        await svc.refresh(db)
        assert site_tips.for_url("https://www.danawa.com").body == "DB 에서 고친 요령"
        assert site_tips.for_url("https://www.danawa.com").vertical == "shopping"
        assert site_tips.vertical("flight").stop_words  # 분야도 DB 에서

        row.status = "draft"  # 초안은 에이전트에게 주지 않는다
        await db.commit()
        await svc.refresh(db)
        assert site_tips.for_url("https://www.danawa.com") is None
        row.status, row.enabled = "verified", False  # 꺼 두면 주지 않는다
        await db.commit()
        await svc.refresh(db)
        assert site_tips.for_url("https://www.danawa.com") is None
    await engine.dispose()


def test_without_cache_files_are_used(clean_cache):
    assert site_tips.all_tips() == tuple(t for t in site_tips.file_tips() if t.status != "draft") and site_tips.all_verticals() == site_tips.file_verticals()
    for t in site_tips.file_tips():  # 분석 전(draft) 사이트는 어느 주소로도 에이전트에게 주어지지 않는다
        if t.status == "draft":
            assert t.name not in {x.name for d in t.domains for x in site_tips.tips_for_url(f"https://www.{d}/")}, t.name


def test_for_url_prefers_the_more_specific_domain(clean_cache):
    site_tips.set_cache([], [
        site_tips.SiteTip(name="검색", domains=("naver.com",), aliases=(), verified="2026-11-01", body="a"),
        site_tips.SiteTip(name="항공", domains=("flight.naver.com",), aliases=(), verified="2026-11-01", body="b"),
    ])
    assert site_tips.for_url("https://flight.naver.com/x").name == "항공"
    assert site_tips.for_url("https://search.naver.com/x").name == "검색"


# ── 한 사이트가 여러 분야를 가질 때 (같은 도메인, 분야마다 한 행) ──────────
def _multi_cache():
    flight = site_tips.Vertical(key="flight", name="항공권", keywords=("항공권",), stop_words=("예약 확정",), stop_urls=(), body="항공 지침")
    hotel = site_tips.Vertical(key="hotel", name="호텔", keywords=("호텔", "숙소"), stop_words=("지금 결제",), stop_urls=(), body="호텔 지침")
    fl = site_tips.SiteTip(name="아고다 · 항공권", domains=("agoda.com",), aliases=("아고다",), verified="2026-11-20", body="항공 요령", vertical="flight",
                           spec={"entry": [{"label": "항공", "url": "https://www.agoda.com/flights"}]})
    ho = site_tips.SiteTip(name="아고다 · 호텔", domains=("agoda.com",), aliases=("아고다",), verified="2026-11-20", body="호텔 요령", vertical="hotel",
                           spec={"entry": [{"label": "호텔", "url": "https://www.agoda.com/hotels"}]})
    other = site_tips.SiteTip(name="검색", domains=("naver.com",), aliases=(), verified="2026-11-20", body="x")
    site_tips.set_cache([flight, hotel], [fl, ho, other])


def test_same_domain_tips_are_narrowed_by_task_keywords():
    _multi_cache()
    try:
        names = lambda task: {t.name for t in site_tips.match_task(task)}
        assert names("아고다에서 호텔 찾아줘") == {"아고다 · 호텔"}
        assert names("agoda.com 항공권 조회") == {"아고다 · 항공권"}
        assert names("아고다 호텔이랑 항공권 같이") == {"아고다 · 항공권", "아고다 · 호텔"}  # 둘 다 말했으면 둘 다
        assert names("아고다 열어줘") == {"아고다 · 항공권", "아고다 · 호텔"}  # 분야를 못 정하면 모두
        blocks, shown = site_tips.start_blocks("아고다에서 숙소 찾아줘")
        assert shown == {"아고다 · 호텔", "@hotel"} and any("호텔 요령" in b for b in blocks) and not any("항공 요령" in b for b in blocks)
    finally:
        site_tips.clear_cache()


def test_same_domain_tips_are_picked_by_shown_vertical_then_path_then_all():
    _multi_cache()
    try:
        assert {t.name for t in site_tips.tips_for_url("https://www.agoda.com/x")} == {"아고다 · 항공권", "아고다 · 호텔"}
        assert [t.name for t in site_tips.pick("https://www.agoda.com/x", {"@hotel"})] == ["아고다 · 호텔"]  # 경로로 못 정하면 이미 안내한 분야
        assert [t.name for t in site_tips.pick("https://www.agoda.com/flights/seoul")] == ["아고다 · 항공권"]  # 주소의 첫 경로
        assert len(site_tips.pick("https://www.agoda.com/")) == 2  # 정할 수 없으면 모두
        assert site_tips.for_url("https://www.agoda.com", {"hotel"}).name == "아고다 · 호텔" and site_tips.for_url("https://www.agoda.com").name == "아고다 · 항공권"
        assert [t.name for t in site_tips.tips_for_url("https://m.naver.com")] == ["검색"]
    finally:
        site_tips.clear_cache()


def test_just_in_time_gives_only_the_unseen_vertical_and_stop_rules_cover_all():
    _multi_cache()
    try:
        shown = {"아고다 · 호텔", "@hotel"}  # 호텔로 시작한 작업이 같은 사이트의 다른 화면으로 이동
        assert site_tips.jit_text("https://www.agoda.com/hotels/x", shown) == ""  # 호텔 요령은 이미 안내했다
        text = site_tips.jit_text("https://www.agoda.com/flights/seoul", shown)  # 항공 화면으로 가면 그 분야의 것을 처음 안내
        assert "[분야 지침 · 항공권]" in text and "항공 요령" in text and "호텔 요령" not in text and "@flight" in shown
        assert site_tips.jit_text("https://www.agoda.com/flights/seoul", shown) == ""  # 한 번만
        words, _ = site_tips.stop_rules("https://www.agoda.com/", set())  # 분야를 못 정해도 같은 도메인 분야의 중단 문구는 모두 적용
        assert set(words) == {"예약 확정", "지금 결제"}
    finally:
        site_tips.clear_cache()

"""웹사이트 분석·재현 검증: 입력 검증, 답변 해석, 판정, 실행 흐름 (에이전트·브라우저는 가짜)."""
import asyncio

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agent import site_tips
from app.db.base import Base
from app.models.site_profile import SiteAnalysisRun, SiteProfile, SiteProfileRevision, SiteVertical
from app.services import site_analysis_service as sa
from app.services import site_profile_service as svc


def test_parse_draft_and_verdict():
    body, notes = sa.parse_draft("앞말\n<요령>\n검색은 `https://x.com/s?q=검색어`\n</요령>\n\n분석 메모: 로그인은 미확인")
    assert body == "검색은 `https://x.com/s?q=검색어`" and notes == "로그인은 미확인"
    assert sa.parse_draft("태그 없음") == ("", "태그 없음")
    v = sa.parse_verdict('끝\n<검증>{"success": true, "summary": "확인함", "issues": ["a", " "]}</검증>')
    assert v == {"success": True, "summary": "확인함", "issues": ["a"], "steps": []}
    v = sa.parse_verdict('<검증>{"success": true, "summary": "s", "steps": [{"key": "Search", "status": "reached", "note": "ok"}, {"key": "x", "status": "weird"}, {"note": "키 없음"}]}</검증>')
    assert v["steps"] == [{"key": "search", "status": "reached", "note": "ok"}, {"key": "x", "status": "failed", "note": ""}]  # 모르는 상태는 실패로 본다
    assert sa.parse_verdict("없음") is None and sa.parse_verdict("<검증>{깨짐</검증>") is None
    # 모델이 닫는 태그를 틀리게 쓰거나(실제로 `}검증>` 로 닫은 적이 있다) 빠뜨려도, 코드 펜스 안에 넣어도 판정은 읽힌다
    for tail in ('}검증>', '}</검증', '}', '}\n```'):
        assert sa.parse_verdict('<검증>{"success": true, "summary": "s"' + tail)["success"] is True, tail
    assert sa.parse_verdict('<검증>\n```json\n{"success": false, "summary": "s"}\n```\n</검증>')["success"] is False
    assert sa.parse_structure('<구조>{"stop_point": "x"}구조>')[0]["stop_point"] == "x"  # 구조도 같다
    assert sa.parse_verdict('<검증>{"success": "yes"}</검증>') is None  # success 는 불리언이어야 한다


def test_parse_structure():
    ok, err = sa.parse_structure('앞\n<구조>\n```json\n{"entry": [{"label": "검색", "url": "https://x.com/?q={query}"}], "stop_point": "결제창"}\n```\n</구조>\n<요령>메모</요령>')
    assert ok["entry"][0]["url"] == "https://x.com/?q={query}" and ok["stop_point"] == "결제창" and err == ""
    for text, why in (("없음", "없습니다"), ("<구조>{깨짐</구조>", "JSON"), ('<구조>{"entry": [{"url": "javascript:x"}]}</구조>', "검증 실패")):
        spec, err = sa.parse_structure(text)
        assert spec == {} and why in err, text
    body, notes = sa.parse_draft('<구조>{"stop_point": "x"}</구조>\n<요령>예외</요령>\n분석 메모: 미확인')  # 구조 블록은 메모에 섞이지 않는다
    assert body == "예외" and notes == "미확인"
    assert sa.parse_draft('<구조>{"stop_point": "x"}</구조>') == ("", "")


FLOW = [{"key": "search", "title": "검색"}, {"key": "compare", "title": "비교"}, {"key": "cart", "title": "담기", "write": True}]


def test_evaluate_judges_each_flow_step_and_skips_write_steps():
    steps = [{"action": "goto", "ok": True}]
    done = {"success": True, "summary": "s", "issues": [], "steps": [{"key": "search", "status": "reached", "note": ""}, {"key": "compare", "status": "reached", "note": ""}]}
    r = sa.evaluate(done, steps, 0, 1, FLOW)
    assert r["passed"] and [f["status"] for f in r["flow"]] == ["reached", "reached", "untested"]  # 상태를 바꾸는 단계는 시험하지 않는다
    partial = {**done, "steps": [done["steps"][0], {"key": "compare", "status": "failed", "note": "막힘"}]}
    r = sa.evaluate(partial, steps, 0, 1, FLOW)
    assert not r["passed"] and r["success"] and "도달하지 못한 단계: 비교" in r["issues"][-1]  # 성공이라 보고해도 단계가 막혔으면 통과가 아니다
    r = sa.evaluate({**done, "steps": done["steps"][:1]}, steps, 0, 1, FLOW)
    assert not r["passed"] and r["flow"][1]["status"] == "missing"  # 보고되지 않은 단계
    assert sa.evaluate({"success": True, "summary": "s", "issues": [], "steps": []}, steps, 0, 1, [])["passed"]  # 분야에 단계 정의가 없으면 보고만 본다


def test_evaluate_requires_reported_success_and_few_loop_blocks():
    steps = [{"action": "goto", "ok": True}, {"action": "click", "ok": False}, {"action": "", "ok": None}]
    ok = sa.evaluate({"success": True, "summary": "s", "issues": []}, steps, 0, 12.34)
    assert ok["passed"] and ok["steps"] == 2 and ok["failed_steps"] == 1 and ok["seconds"] == 12.3
    assert not sa.evaluate({"success": False, "summary": "s", "issues": []}, steps, 0, 1)["passed"]
    looped = sa.evaluate({"success": True, "summary": "s", "issues": []}, steps, 3, 1)
    assert not looped["passed"] and looped["success"] and "반복" in looped["issues"][-1]
    none = sa.evaluate(None, steps, 0, 1)
    assert not none["passed"] and "보고하지 않았습니다" in none["summary"]


def test_fold_event_builds_steps_with_results():
    steps: list = []
    assert sa.fold_event(steps, {"type": "tool_call", "tool": "browser_action", "call_id": "c1", "ts": 1, "input": {"action": "goto", "desc": "이동 · x.com", "url": "https://x.com"}})
    assert sa.fold_event(steps, {"type": "tool_result", "tool": "browser_action", "call_id": "c1", "ts": 5, "success": False, "output": "Error: 실패"})
    assert steps == [{"id": "c1", "action": "goto", "desc": "이동 · x.com", "url": "https://x.com", "ok": False, "brief": "Error: 실패", "t0": 1, "t1": 5}]
    assert not sa.fold_event(steps, {"type": "tool_call", "tool": "other", "call_id": "z"})  # 브라우저 도구가 아니면 무시


def test_normalize_url():
    assert sa.normalize_url("www.danawa.com") == "https://www.danawa.com"
    for bad in ("", "ftp://x.com", "localhost", "http://"):
        with pytest.raises(sa.AnalysisError):
            sa.normalize_url(bad)


@pytest_asyncio.fixture
async def db(monkeypatch):
    site_tips.clear_cache()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[SiteVertical.__table__, SiteProfile.__table__, SiteProfileRevision.__table__, SiteAnalysisRun.__table__]))
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    import app.db.session as dbs

    monkeypatch.setattr(dbs, "AsyncSessionLocal", maker)  # 백그라운드 실행이 같은 메모리 DB 를 쓰게 한다
    async with maker() as s:
        await svc.seed_from_files(s)
        await svc.refresh(s)
        yield s
    await engine.dispose()
    site_tips.clear_cache()


def req(**kw):
    return {"mode": "analyze", "name": "테스트 항공", "vertical": "flight", "start_url": "air.testfly.com", "scenario": "김포→제주 성인 1명 가격순 조회", **kw}


@pytest.mark.asyncio
async def test_start_validates_input_and_allows_one_run_per_user(db, monkeypatch):
    started = []

    async def fake_execute(run_id, current_body=""):
        started.append(run_id)
        await asyncio.sleep(0.2)

    monkeypatch.setattr(sa, "_execute", fake_execute)
    cases = [(req(mode="x"), 400), (req(name=" "), 400), (req(start_url="nope"), 400), (req(scenario="짧"), 400), (req(vertical="nope"), 404), (req(mode="verify"), 400),
             (req(draft_spec={"entry": [{"url": "javascript:x"}]}), 400), (req(vertical=None, scenario=""), 400)]
    for data, status in cases:
        with pytest.raises(sa.AnalysisError) as e:
            await sa.start(db, "u1", data)
        assert e.value.status == status, data
    run = await sa.start(db, "u1", req())
    assert run.status == "running" and run.start_url == "https://air.testfly.com"
    with pytest.raises(sa.AnalysisError) as e:
        await sa.start(db, "u1", req())  # 이미 실행 중
    assert e.value.status == 409
    other = await sa.start(db, "u2", req(scenario="", inputs={"origin": "부산", "zzz": " "}))  # 다른 사용자는 따로다. 분야가 있으면 시나리오를 비워도 된다
    assert other.scenario == sa.DEFAULT_SCENARIO and other.inputs == {"origin": "부산"}
    assert other.id != run.id
    await asyncio.sleep(0.3)
    assert len(started) == 2
    assert (await sa.get_run(db, "u1", run.id)).id == run.id
    with pytest.raises(sa.AnalysisError):
        await sa.get_run(db, "u2", run.id)  # 남의 실행은 볼 수 없다


class FakeAgent:
    answer = ""
    last_kwargs: dict = {}

    def __init__(self, **kw):
        FakeAgent.last_kwargs = kw

    async def arun(self, prompt):
        FakeAgent.prompt = prompt
        from app.agent import side_events

        side_events.emit("siteanalysis:" + FakeAgent.run_id, {"type": "tool_call", "tool": "browser_action", "call_id": "c1", "input": {"action": "goto", "desc": "이동"}})
        side_events.emit("siteanalysis:" + FakeAgent.run_id, {"type": "tool_result", "tool": "browser_action", "call_id": "c1", "success": True, "output": "URL: x"})
        await asyncio.sleep(0.05)

        class R:
            content = FakeAgent.answer

        return R()


async def run_fake(db, monkeypatch, mode, answer, **kw):
    import agno.agent as agno_agent

    monkeypatch.setattr(agno_agent, "Agent", FakeAgent)
    monkeypatch.setattr("app.agent.agno_engine.build_agno_model", lambda *a, **k: object())
    monkeypatch.setattr("app.agent.agno_engine.to_agno_function", lambda t: t)
    FakeAgent.answer = answer
    orig = sa.SiteAnalysisRun

    run = await sa.start(db, "u1", req(mode=mode, **kw))
    FakeAgent.run_id = run.id
    await sa._tasks[run.id]
    await db.refresh(run)
    return run


@pytest.mark.asyncio
async def test_analyze_run_stores_draft_and_steps(db, monkeypatch):
    # 실행이 시작되기 전에 run_id 를 알아야 하므로 에이전트가 만들어질 때 id 를 받는다
    run = await run_fake(db, monkeypatch, "analyze", '<구조>{"entry": [{"label": "검색", "url": "https://x/?o={origin}"}], "inputs": {"origin": {"how": "자동완성", "param": "o"}}}</구조>\n<요령>\n예외는 이것\n</요령>\n분석 메모: 미확인 있음',
                         current_body="이전 요령", draft_spec={"stop_point": "이전 멈춤"}, inputs={"origin": "부산"})
    assert run.status == "succeeded" and run.draft_body == "예외는 이것" and "미확인" in run.answer
    assert run.draft_spec["inputs"]["origin"]["param"] == "o" and run.draft_spec["entry"][0]["label"] == "검색"
    assert "- 출발지 (origin): 부산" in FakeAgent.prompt and "trip_type: 왕복/편도" not in FakeAgent.prompt and "search: 조건 입력·검색" in FakeAgent.prompt  # 입력값(덮어쓴 값)과 표준 단계가 프롬프트에 들어간다
    assert "이전 멈춤" in FakeAgent.prompt
    assert run.browser_run and [s["desc"] for s in run.steps] == ["이동"] and run.steps[0]["ok"] is True
    ins = "\n".join(FakeAgent.last_kwargs["instructions"])
    assert "[분야 지침 · 항공권]" in ins  # 분야 지침이 지침에 붙는다
    assert "이전 요령" in FakeAgent.prompt and "분석 시나리오" in FakeAgent.prompt


@pytest.mark.asyncio
async def test_analyze_without_the_tag_fails_with_the_raw_answer_kept(db, monkeypatch):
    run = await run_fake(db, monkeypatch, "analyze", "형식을 안 지킨 답")
    assert run.status == "failed" and "형식" in run.error and run.answer == "형식을 안 지킨 답"
    only = await run_fake(db, monkeypatch, "analyze", '<구조>{"stop_point": "결제창"}</구조>')  # 구조만 있어도 초안이다
    assert only.status == "succeeded" and only.draft_spec == {"entry": [], "menus": [], "inputs": {}, "flow": [], "stop_point": "결제창"} and not only.draft_body


@pytest.mark.asyncio
async def test_verify_run_tests_the_draft_and_judges(db, monkeypatch):
    verdict = '{"success": true, "summary": "가격 확인", "issues": [], "steps": [{"key": "search", "status": "reached"}, {"key": "sort", "status": "reached"}, {"key": "compare", "status": "reached"}, {"key": "select", "status": "reached"}, {"key": "stop", "status": "reached"}]}'
    run = await run_fake(db, monkeypatch, "verify", f"수행함\n<검증>{verdict}</검증>", draft_body="시험할 요령 본문", draft_spec={"stop_point": "예약처 선택 화면"}, inputs={"origin": "부산"})
    assert run.status == "succeeded" and run.result["passed"] is True and run.result["steps"] == 1
    assert [f["status"] for f in run.result["flow"]] == ["reached", "reached", "reached", "untested", "reached"]  # 항공편 선택은 쓰기 단계라 보고와 무관하게 시험 안 함
    ins = "\n".join(FakeAgent.last_kwargs["instructions"])
    assert "시험할 요령 본문" in ins and "[사이트 요령 · 테스트 항공" in ins and "[분야 지침 · 항공권]" in ins and "멈출 지점: 예약처 선택 화면" in ins
    assert "- 출발지 (origin): 부산" in FakeAgent.prompt and "- 도착지 (destination): 도쿄(NRT)" in FakeAgent.prompt  # 입력값은 직접 준 것이 샘플보다 우선하고, 나머지는 분야 샘플
    short = await run_fake(db, monkeypatch, "verify", '<검증>{"success": true, "summary": "s", "steps": [{"key": "search", "status": "reached"}]}</검증>', draft_body="x")
    assert short.result["passed"] is False and short.result["flow"][1]["status"] == "missing"  # 성공이라 해도 단계 보고가 빠지면 통과가 아니다
    bad = await run_fake(db, monkeypatch, "verify", "판정 없이 끝", draft_body="x")
    assert bad.result["passed"] is False and "보고하지 않았습니다" in bad.result["summary"]


@pytest.mark.asyncio
async def test_cancel_marks_the_run_cancelled(db, monkeypatch):
    import agno.agent as agno_agent

    class Slow(FakeAgent):
        async def arun(self, prompt):
            await asyncio.sleep(30)

    monkeypatch.setattr(agno_agent, "Agent", Slow)
    monkeypatch.setattr("app.agent.agno_engine.build_agno_model", lambda *a, **k: object())
    monkeypatch.setattr("app.agent.agno_engine.to_agno_function", lambda t: t)
    run = await sa.start(db, "u1", req())
    await asyncio.sleep(0.2)
    out = await sa.cancel(db, "u1", run.id)
    assert out.status == "cancelled" and out.finished_at is not None
    again = await sa.start(db, "u1", req())  # 끝났으니 새로 시작할 수 있다
    await sa.cancel(db, "u1", again.id)


@pytest.mark.asyncio
async def test_interrupted_runs_are_closed_on_startup(db):
    run = SiteAnalysisRun(user_id="u1", mode="analyze", name="x", start_url="https://x.com", scenario="시나리오 입니다", status="running")
    db.add(run)
    await db.commit()
    await sa.mark_interrupted()
    await db.refresh(run)
    assert run.status == "failed" and "다시 시작" in run.error


@pytest.mark.asyncio
async def test_real_browser_tool_events_fold_into_steps_and_payment_is_blocked(monkeypatch):
    """실제 BrowserActionTool 이 내보내는 진행 이벤트가 분석 단계 목록이 되고, 분야 stop_words 가 분석 실행에도 적용된다."""
    from app.agent import side_events
    from app.tools import browser_tools as bt

    els = [{"ref": 1, "tag": "button", "label": "예약 확정"}, {"ref": 2, "tag": "button", "label": "검색"}]
    calls = []

    async def fake_call(user_id, payload, **kw):
        calls.append(payload["cmd"])
        return {"ok": True, "url": "https://air.testfly.com/x", "title": "t", "elements": els, "text": "본문"}

    monkeypatch.setattr(bt, "browser_call", fake_call)
    site_tips.clear_cache()
    conv = "siteanalysis:test"
    q = side_events.open_channel(conv)
    try:
        tool = bt.BrowserActionTool(user_id="u1", conversation_id=conv, login_enabled=False, run_tag="abc", tips_shown={"테스트 항공", "@flight"})
        await tool._arun("goto", url="https://air.testfly.com/x")
        blocked = await tool._arun("click", ref=1)  # 항공 분야의 stop_words('예약 확정')
        steps: list = []
        while not q.empty():
            sa.fold_event(steps, q.get_nowait())
    finally:
        side_events.close_channel(conv, q)
    assert blocked.startswith("[결제 직전]") and calls.count("click") == 0
    assert [s["action"] for s in steps] == ["goto", "click"] and all(s["ok"] is not None for s in steps)
    assert steps[1]["ok"] is False  # 막힌 동작은 실패 단계로 남는다


@pytest.mark.asyncio
async def test_captcha_handoff_option_is_stored_and_given_to_the_browser_tool(db, monkeypatch):
    off = await run_fake(db, monkeypatch, "analyze", '<구조>{"stop_point": "x"}</구조>')
    assert off.captcha_handoff is False and FakeAgent.last_kwargs["tools"][0].captcha_handoff is False  # 기본은 넘기지 않는다
    on = await run_fake(db, monkeypatch, "analyze", '<구조>{"stop_point": "x"}</구조>', captcha_handoff=True)
    assert on.captcha_handoff is True and FakeAgent.last_kwargs["tools"][0].captcha_handoff is True
    assert FakeAgent.last_kwargs["tools"][0].login_enabled is False  # 쓰기 동작 승인은 켜지지 않는다 (읽기 전용 유지)


def test_captcha_handoff_waits_for_the_user_but_still_blocks_write_approvals(monkeypatch):
    from app.core.login_requests import PendingLogins
    from app.tools import browser_tools as bt

    calls = []

    async def fake_call(user_id, payload, timeout=90, sandbox_cid="", use_profile=True, session_id=""):
        calls.append(payload["cmd"])
        if payload["cmd"] == "goto":
            return {"ok": True, "url": "https://shop.test/captcha/1", "title": "t", "elements": [], "text": ""}
        return {"ok": True, "url": "https://shop.test/results", "title": "ok", "elements": [], "text": "results"}

    monkeypatch.setattr(bt, "browser_call", fake_call)

    async def run(handoff):
        tool = bt.BrowserActionTool(user_id="u1", conversation_id="c-cap-h", login_enabled=False, captcha_handoff=handoff)
        task = asyncio.create_task(tool._arun("goto", url="https://shop.test/"))
        await asyncio.sleep(0.05)
        if handoff:
            assert PendingLogins.get("c-cap-h", "u1")["site"] == "shop.test"  # 화면이 이 요청을 보고 사용자가 해결한다
            PendingLogins.resolve("c-cap-h", "u1")
        return tool, await task

    tool, out = asyncio.run(run(True))
    assert "해결했습니다" in out and "results" in out
    _, out = asyncio.run(run(False))
    assert "captcha" in out  # 옵션이 꺼져 있으면 기다리지 않는다
    from app.services import browser_policy

    monkeypatch.setattr(browser_policy, "needs_approval", lambda *a, **k: True)  # 승인이 필요한 쓰기 동작이 왔을 때
    msg = asyncio.run(tool._approve({"cmd": "click"}))
    assert msg and "승인할 수 있는 화면이 없어 실행하지 않았습니다" in msg  # 캡차 옵션을 켜도 쓰기 동작은 승인 요청 없이 막힌다


@pytest.mark.asyncio
async def test_clean_session_option_uses_the_sandbox_without_the_profile(db, monkeypatch):
    from app.services import local_browser as lb

    closed = []

    async def fake_browser_call(user_id, payload, timeout=90, sandbox_cid="", use_profile=True, session_id=""):
        closed.append((payload["cmd"], use_profile))
        return {"ok": True}

    import app.tools.browser_tools as bt

    monkeypatch.setattr(bt, "browser_call", fake_browser_call)
    seen = {}
    orig = FakeAgent.arun

    async def spy(self, prompt):
        seen["forced"] = lb._force_sandbox.get()  # 분석 태스크 안에서는 로컬 브라우저 대신 sandbox 로 보낸다
        return await orig(self, prompt)

    monkeypatch.setattr(FakeAgent, "arun", spy)
    off = await run_fake(db, monkeypatch, "analyze", '<구조>{"stop_point": "x"}</구조>')
    assert off.clean_session is False and FakeAgent.last_kwargs["tools"][0].use_profile is True and seen["forced"] is False and not closed
    on = await run_fake(db, monkeypatch, "analyze", '<구조>{"stop_point": "x"}</구조>', clean_session=True)
    assert on.clean_session is True and FakeAgent.last_kwargs["tools"][0].use_profile is False and seen["forced"] is True
    assert ("close", False) in closed  # 이전 실행의 브라우저 세션을 버리고 시작한다
    assert lb._force_sandbox.get() is False  # 분석 태스크 밖(서버의 다른 요청)에는 영향이 없다
    with pytest.raises(sa.AnalysisError) as e:
        await sa.start(db, "u1", req(clean_session=True, captcha_handoff=True))  # 깨끗한 환경에서는 캡차를 넘길 화면이 없다
    assert e.value.status == 400


@pytest.mark.asyncio
async def test_route_for_skips_the_local_browser_when_forced(monkeypatch):
    from app.config import settings
    from app.services import local_browser as lb

    monkeypatch.setattr(settings, "LOCAL_BROWSER_USER_ID", "u1")
    monkeypatch.setattr(settings, "LOCAL_BROWSER_CDP_URL", "http://127.0.0.1:9")

    async def avail(self):
        return True

    monkeypatch.setattr(lb.LocalBrowser, "available", avail)
    assert await lb.route_for("u1") is not None

    async def forced():
        lb.force_sandbox()
        return await lb.route_for("u1")

    assert await asyncio.create_task(forced()) is None  # 강제한 태스크만
    assert await lb.route_for("u1") is not None

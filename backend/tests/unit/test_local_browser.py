"""로컬 브라우저(CDP) — 키 매핑, 라우팅 규칙, 명령 처리 (CDP 연결은 가짜로 대체)."""
import pytest

from app.config import settings
from app.services import local_browser as lb


def test_key_spec_named_and_char():
    assert lb.key_spec("Enter")["windowsVirtualKeyCode"] == 13
    assert lb.key_spec("Enter")["text"] == "\r"
    assert lb.key_spec("Escape").get("text") is None
    a = lb.key_spec("a")
    assert a["code"] == "KeyA" and a["text"] == "a"
    with pytest.raises(ValueError):
        lb.key_spec("NoSuchKey")


class FakeBrowser(lb.LocalBrowser):
    def __init__(self):
        super().__init__("http://127.0.0.1:9222")
        self.calls: list[tuple[str, dict]] = []
        self.values: dict[str, object] = {}

    async def _connect(self):  # 실제 연결 없음
        return None

    async def _send(self, method, params=None, timeout=30.0):
        self.calls.append((method, params or {}))
        if method == "Page.navigate":
            return {}
        if method == "Page.getNavigationHistory":
            return {"currentIndex": 0, "entries": [{"id": 1}]}
        return {}

    async def _eval(self, expression, timeout=15.0):
        if "readyState" in expression:
            return "complete"
        if "location.href" in expression:
            return "https://example.com/"
        if "document.title" in expression:
            return "Example"
        if "elementFromPoint" in expression and "scrollIntoView" in expression:  # 요소 위치 계산 (눌러도 되는 자리인지 확인 포함)
            return self.values.get("eval")
        if "elements" in expression or "data-agent-ref" in expression and "querySelectorAll" in expression:
            return {"elements": [{"ref": 1, "tag": "a", "label": "x"}], "text": "hi"}
        return self.values.get("eval")


@pytest.mark.asyncio
async def test_goto_rejects_non_http_and_private(monkeypatch):
    b = FakeBrowser()
    assert (await b.handle({"cmd": "goto", "url": "file:///etc/passwd"}))["ok"] is False
    monkeypatch.setattr(lb, "_is_blocked_host", lambda h: True)
    monkeypatch.setattr(settings, "LOCAL_BROWSER_ALLOW_PRIVATE", False)
    r = await b.handle({"cmd": "goto", "url": "http://10.0.0.1/"})
    assert r["ok"] is False and "blocked" in r["error"]
    assert not any(m == "Page.navigate" for m, _ in b.calls)


@pytest.mark.asyncio
async def test_goto_returns_snapshot(monkeypatch):
    monkeypatch.setattr(lb, "_is_blocked_host", lambda h: False)
    b = FakeBrowser()
    r = await b.handle({"cmd": "goto", "url": "https://example.com"})
    assert r["ok"] and r["url"] == "https://example.com/" and r["elements"][0]["ref"] == 1


@pytest.mark.asyncio
async def test_click_missing_ref_reports_error():
    b = FakeBrowser()
    b.values["eval"] = None  # 요소를 못 찾음
    r = await b.handle({"cmd": "click", "ref": 9})
    assert r["ok"] is False and "ref 9" in r["error"]


@pytest.mark.asyncio
async def test_back_without_history():
    r = await FakeBrowser().handle({"cmd": "back"})
    assert r["ok"] is False


@pytest.mark.asyncio
async def test_close_and_export_do_not_touch_user_browser():
    b = FakeBrowser()
    assert (await b.handle({"cmd": "close"}))["ok"] is True
    assert (await b.handle({"cmd": "export_state"}))["ok"] is False
    assert b.calls == []


@pytest.mark.asyncio
async def test_route_only_for_configured_user(monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_BROWSER_CDP_URL", "http://127.0.0.1:9222")
    monkeypatch.setattr(settings, "LOCAL_BROWSER_USER_ID", "u1")

    async def up(self):
        return True

    monkeypatch.setattr(lb.LocalBrowser, "available", up)
    assert await lb.route_for("someone-else") is None
    assert await lb.route_for("u1") is not None
    monkeypatch.setattr(settings, "LOCAL_BROWSER_USER_ID", "")
    assert await lb.route_for("u1") is None


@pytest.mark.asyncio
async def test_route_falls_back_when_app_not_running(monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_BROWSER_CDP_URL", "http://127.0.0.1:9222")
    monkeypatch.setattr(settings, "LOCAL_BROWSER_USER_ID", "u1")

    async def down(self):
        return False

    monkeypatch.setattr(lb.LocalBrowser, "available", down)
    assert await lb.route_for("u1") is None  # → sandbox 브라우저 사용


@pytest.mark.asyncio
async def test_user_stop_blocks_same_run_until_new_run():
    b = FakeBrowser()
    stops = iter([False, True, False, False])

    async def act():
        return next(stops)

    b._activity = act
    assert (await b.handle({"cmd": "snapshot", "run": "r1"}))["ok"] is True          # 정상
    r = await b.handle({"cmd": "snapshot", "run": "r1"})                              # 중지 신호
    assert r["ok"] is False and "중지" in r["error"]
    assert (await b.handle({"cmd": "snapshot", "run": "r1"}))["ok"] is False          # 같은 작업은 계속 거부
    assert (await b.handle({"cmd": "snapshot", "run": "r2"}))["ok"] is True           # 새 작업은 허용


@pytest.mark.asyncio
async def test_login_handoff_in_local_mode_marks_info_and_sets_attention(monkeypatch):
    import asyncio

    from app.core.login_requests import PendingLogins
    from app.tools.browser_tools import WaitClock

    calls: list[str] = []

    class Stub:
        async def set_attention(self, msg):
            calls.append(msg)

    async def route(user_id, sid=""):
        return Stub()

    monkeypatch.setattr(lb, "route_for", route)
    clock = WaitClock()

    async def user():
        for _ in range(50):
            await asyncio.sleep(0.02)
            info = PendingLogins.get("cv", "u1")
            if info:
                assert info["local"] is True and info["site"] == "LinkedIn"
                PendingLogins.resolve("cv", "u1")
                return

    t = asyncio.create_task(user())
    res = await clock.ask("cv", "u1", {"site": "LinkedIn", "url": "", "reason": ""}, 5)
    await t
    assert res == {"done": True}
    assert len(calls) == 2 and "LinkedIn" in calls[0] and calls[1] == ""  # 안내 표시 → 해제


@pytest.mark.asyncio
async def test_approval_in_local_mode_does_not_set_attention(monkeypatch):
    import asyncio

    from app.core.login_requests import PendingLogins
    from app.tools.browser_tools import WaitClock

    calls: list[str] = []

    class Stub:
        async def set_attention(self, msg):
            calls.append(msg)

    async def route(user_id, sid=""):
        return Stub()

    monkeypatch.setattr(lb, "route_for", route)

    async def user():
        for _ in range(50):
            await asyncio.sleep(0.02)
            if PendingLogins.get("cv2", "u1"):
                PendingLogins.resolve("cv2", "u1")
                return

    t = asyncio.create_task(user())
    await WaitClock().ask("cv2", "u1", {"kind": "approval", "site": "x"}, 5, count=False)
    await t
    assert calls == []


@pytest.mark.asyncio
async def test_browser_local_note_only_when_local_browser_connected(monkeypatch):
    from app.agent.orchestrator import browser_local_note

    async def up(user_id, sid=""):
        return object()

    async def down(user_id, sid=""):
        return None

    monkeypatch.setattr(lb, "route_for", up)
    note = await browser_local_note("u1", True)
    assert "우측" in note and "cli_browser_agent" in note
    assert await browser_local_note("u1", False) == ""  # 브라우저 도구가 없는 실행(예약 등)에는 붙이지 않는다
    monkeypatch.setattr(lb, "route_for", down)
    assert await browser_local_note("u1", True) == ""


def test_browser_routing_guidance_present_in_prompts_and_tool_descriptions():
    from app.agent import prompts
    from app.tools.browser_tools import CliBrowserAgentTool
    from app.tools.crawler import WebCrawlerTool

    system = prompts.load("system")
    assert "브라우저로" in system and "web_crawler" in system and "403" in system
    assert any("ResearchAgent" in p and "cli_browser_agent" in p for p in prompts.sections("team_default"))
    assert "USE THIS" in CliBrowserAgentTool().description
    assert "cli_browser_agent" in WebCrawlerTool().description


# ── 병렬 브라우저 ─────────────────────────────────────────────────────────────
def test_site_key_groups_same_site_and_handles_unknown():
    from app.tools.browser_tools import site_key

    assert site_key("가격", "https://www.coupang.com/np/search?q=a") == "coupang.com"
    assert site_key("가격", "https://m.coupang.com/x") == "coupang.com"  # 하위 도메인은 같은 사이트
    assert site_key("가격", "https://shopping.naver.com/") == "naver.com"
    assert site_key("가격", "https://www.gmarket.co.kr/") == "gmarket.co.kr"  # co.kr 은 세 단계
    assert site_key("https://www.11st.co.kr 에서 확인", None) == "11st.co.kr"  # 작업 문장 속 주소
    assert site_key("어딘가에서 가격 확인", None) is None


@pytest.mark.asyncio
async def test_browser_parallel_runs_distinct_sites_concurrently_and_same_site_sequentially(monkeypatch):
    import asyncio

    from app.services import local_browser as lb
    from app.tools import browser_tools as bt

    async def route(user_id, sid=""):
        return object()  # 로컬 브라우저 연결됨

    monkeypatch.setattr(lb, "route_for", route)
    running, peak, order = 0, 0, []

    async def fake_arun(self, task, start_url=None, new_session=False):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        order.append(("start", start_url))
        await asyncio.sleep(0.05)
        running -= 1
        order.append(("end", start_url))
        return f"done {start_url} sid={'y' if self.session_id else 'n'}"

    monkeypatch.setattr(bt.CliBrowserAgentTool, "_arun", fake_arun)
    tool = bt.BrowserParallelTool(user_id="u1", conversation_id="c1")
    out = await tool._arun([
        {"task": "a", "start_url": "https://a.com/1"},
        {"task": "b", "start_url": "https://b.com/"},
        {"task": "c", "start_url": "https://www.a.com/2"},  # a.com 과 같은 사이트 → a.com/1 이 끝난 뒤에 시작
        {"task": "d", "start_url": "https://d.com/"},
        {"task": "e", "start_url": "https://e.com/"},
    ])
    assert peak <= 3  # 동시 세션 상한
    assert order.index(("end", "https://a.com/1")) < order.index(("start", "https://www.a.com/2"))
    assert out.index("a.com/1") < out.index("b.com") < out.index("www.a.com/2") < out.index("d.com")  # 입력 순서대로 정리
    assert "sid=y" in out


@pytest.mark.asyncio
async def test_browser_parallel_falls_back_to_sequential_without_local_browser(monkeypatch):
    import asyncio

    from app.services import local_browser as lb
    from app.tools import browser_tools as bt

    async def route(user_id, sid=""):
        return None

    monkeypatch.setattr(lb, "route_for", route)
    running, peak = 0, 0

    async def fake_arun(self, task, start_url=None, new_session=False):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.02)
        running -= 1
        return f"ok sid={'y' if self.session_id else 'n'}"

    monkeypatch.setattr(bt.CliBrowserAgentTool, "_arun", fake_arun)
    out = await bt.BrowserParallelTool(user_id="u1")._arun([{"task": "a", "start_url": "https://a.com"}, {"task": "b", "start_url": "https://b.com"}])
    assert peak == 1 and "sid=y" not in out


@pytest.mark.asyncio
async def test_stop_is_seen_by_every_session_via_stop_count(monkeypatch):
    from app.services.local_browser import LocalBrowser

    state = {"seq": 0}
    monkeypatch.setattr(LocalBrowser, "_post_body", staticmethod(lambda url, body, timeout=2.0: {"stop": False, "stopSeq": state["seq"], "opened": False}))
    a, b = LocalBrowser("http://x", sid="a"), LocalBrowser("http://x", sid="b")
    assert await a._activity() is False and await b._activity() is False  # 처음 본 값은 기준일 뿐
    state["seq"] = 1  # 사용자가 '중지'를 눌렀다
    assert await a._activity() is True and await b._activity() is True  # 한 세션이 먼저 읽어도 다른 세션도 멈춘다
    assert await a._activity() is False  # 같은 중지를 두 번 처리하지 않는다


def test_browser_parallel_is_a_leader_tool():
    # 팀 리더에게 노출되지 않으면 모델이 병렬 도구를 아예 볼 수 없다 (cli_browser_agent 만 반복 호출하게 된다)
    from app.agent.agno_engine import LEADER_TOOLS

    assert "browser_parallel" in LEADER_TOOLS and "cli_browser_agent" in LEADER_TOOLS


@pytest.mark.asyncio
async def test_navigation_timeout_returns_clear_error(monkeypatch):
    from app.services.local_browser import LocalBrowser, LocalBrowserError

    lb = LocalBrowser("http://127.0.0.1:9")

    async def fake_connect():
        return None

    async def slow(method, params=None, timeout=30.0):
        raise LocalBrowserError(f"CDP 응답 시간 초과: {method}")

    monkeypatch.setattr(lb, "_connect", fake_connect)
    monkeypatch.setattr(lb, "_send", slow)
    res = await lb.handle({"cmd": "goto", "url": "https://example.com/"})
    assert res["ok"] is False and "응답하지 않습니다" in res["error"] and "반복" in res["error"]


@pytest.mark.asyncio
async def test_concurrent_cli_browser_calls_get_own_sessions_and_same_site_waits(monkeypatch):
    import asyncio

    from app.config import settings
    from app.tools import browser_tools as bt

    monkeypatch.setattr(settings, "LOCAL_BROWSER_CDP_URL", "http://127.0.0.1:9222")
    monkeypatch.setattr(settings, "LOCAL_BROWSER_USER_ID", "u1")
    bt._SCHED.inflight.clear()
    seen, running, peak = [], 0, 0

    async def fake_session(self, task, start_url=None, new_session=False):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        seen.append((start_url, self.session_id))
        await asyncio.sleep(0.05)
        running -= 1
        return "ok"

    monkeypatch.setattr(bt.CliBrowserAgentTool, "_arun_session", fake_session)
    tool = bt.CliBrowserAgentTool(user_id="u1", conversation_id="c")
    # 혼자 실행: 기본 브라우저(세션 없음)
    await tool._arun("t", "https://a.com")
    assert seen[-1] == ("https://a.com", "")
    # 같은 턴에 동시에 3번 호출(모델의 병렬 도구 호출): 각자 전용 세션, 같은 사이트(a.com 두 개)는 순서대로
    seen.clear()
    await asyncio.gather(tool._arun("t", "https://a.com/1"), tool._arun("t", "https://b.com"), tool._arun("t", "https://www.a.com/2"))
    assert all(sid for _, sid in seen) and len({sid for _, sid in seen}) == 3
    assert peak == 2  # a.com 두 작업은 겹치지 않아 b.com 과 합쳐 최대 2개
    assert bt._SCHED.inflight["u1"] == 0


@pytest.mark.asyncio
async def test_tabs_are_reset_once_at_the_first_browser_use_of_a_new_request(monkeypatch):
    import asyncio

    from app.config import settings
    from app.services import local_browser as lb

    monkeypatch.setattr(settings, "LOCAL_BROWSER_CDP_URL", "http://127.0.0.1:9222")
    monkeypatch.setattr(settings, "LOCAL_BROWSER_USER_ID", "u1")
    lb._fresh_users.clear()
    events = []

    class Fake:
        async def reset_tabs(self):
            events.append("reset-start")
            await asyncio.sleep(0.05)
            events.append("reset-end")

    async def route(user_id, sid=""):
        return Fake()

    monkeypatch.setattr(lb, "route_for", route)
    await lb.reset_if_new_turn("u1")
    assert events == []  # 새 요청 표시가 없으면(브라우저를 안 쓰는 요청 등) 탭을 건드리지 않는다
    lb.mark_new_turn("someone-else")
    assert not lb._fresh_users  # 앱 브라우저 사용자가 아니면 표시하지 않는다
    lb.mark_new_turn("u1")
    await asyncio.gather(lb.reset_if_new_turn("u1"), lb.reset_if_new_turn("u1"), lb.reset_if_new_turn("u1"))
    assert events == ["reset-start", "reset-end"]  # 동시 호출이어도 한 번만, 나머지는 끝날 때까지 대기
    await lb.reset_if_new_turn("u1")
    assert events == ["reset-start", "reset-end"]  # 같은 요청의 다음 브라우저 사용은 탭을 닫지 않는다


def test_old_snapshots_are_compacted_but_latest_stays_full():
    from agno.models.message import Message

    from app.services.browser_policy import fence_untrusted
    from app.tools.browser_tools import _format, _make_compression_manager, compact_snapshot

    res = {"ok": True, "url": "https://x.com/a", "title": "T", "elements": [{"ref": i, "tag": "a", "label": f"링크 {i}", "href": "https://x.com/" + "p" * 80} for i in range(120)],
           "text": "본문 " * 500}
    big = _format(res)
    assert len(big) > 10000
    small = compact_snapshot(big)
    assert len(small) < 1200 and "URL: https://x.com/a" in small and "Title: T" in small and '"ref": 5' not in small and "본문" in small
    assert compact_snapshot("짧은 결과") == "짧은 결과"  # 짧은 결과는 그대로

    msgs = [Message(role="tool", content=big, tool_name="browser_action") for _ in range(5)]
    mgr = _make_compression_manager()
    assert mgr.should_compress(msgs)
    mgr.compress(msgs)
    assert all(m.compressed_content for m in msgs[:-1]) and msgs[-1].compressed_content is None  # 가장 최근 화면은 그대로
    assert sum(len(m.get_content(use_compressed_content=True) or "") for m in msgs) < 2 * len(big)  # 5개가 전부 쌓이지 않는다


@pytest.mark.asyncio
async def test_pet_gateway_error_body_is_reported_not_a_nonetype_crash():
    from openai.types.chat import ChatCompletion

    from agno.exceptions import ModelProviderError
    from app.agent.agno_engine import build_agno_model
    from app.config import settings

    settings_pet = settings.PET_AGENT_URL
    assert settings_pet  # 테스트 환경에도 설정돼 있어야 모델 객체를 만들 수 있다
    model = build_agno_model("pet")
    bad = ChatCompletion.model_construct(**{"state": 702, "res": {"message": "External server model error"}})
    with pytest.raises(ModelProviderError) as ei:
        model._parse_provider_response(bad)
    assert "게이트웨이" in str(ei.value) and "External server model error" in str(ei.value)


@pytest.mark.asyncio
async def test_side_events_are_merged_into_the_stream_in_arrival_order():
    import asyncio

    from app.agent import side_events

    q = side_events.open_channel("conv-x")

    async def team():
        yield "t1"
        await asyncio.sleep(0.05)
        side_events.emit("conv-x", {"type": "tool_call", "tool": "browser_action"})
        await asyncio.sleep(0.05)
        yield "t2"

    got = [(k, e) async for k, e in side_events.merge_stream(team(), q)]
    side_events.close_channel("conv-x", q)
    assert [k for k, _ in got] == ["team", "side", "team"] and got[1][1]["tool"] == "browser_action"
    side_events.emit("conv-x", {"type": "x"})  # 닫힌 통로에는 아무 일도 하지 않는다


@pytest.mark.asyncio
async def test_browser_action_emits_agent_tagged_steps_with_short_output(monkeypatch):
    from app.agent import side_events
    from app.tools import browser_tools as bt

    q = side_events.open_channel("conv-y")

    async def fake_call(user_id, payload, timeout=90, sandbox_cid="", use_profile=True, session_id=""):
        return {"ok": True, "url": "https://x.com/", "title": "T", "elements": [{"ref": i, "tag": "a", "label": "링크"} for i in range(120)], "text": "본문 " * 800}

    monkeypatch.setattr(bt, "browser_call", fake_call)
    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", lambda self: _false())
    tool = bt.BrowserActionTool(user_id="u1", conversation_id="conv-y", session_label="google.com")
    out = await tool._arun("goto", url="https://x.com/")
    side_events.close_channel("conv-y", q)
    evs = [q.get_nowait() for _ in range(q.qsize())]
    assert len(out) > 2000 and "Interactive elements" in out  # 모델에게는 전체 스냅샷 (요소는 한 줄 형식으로 압축돼 예전보다 짧다)
    assert [e["type"] for e in evs] == ["tool_call", "tool_result"] and evs[0]["call_id"] == evs[1]["call_id"]
    assert all(e["agent"] == "BrowserAgent · google.com" and e["tool"] == "browser_action" for e in evs)
    assert evs[0]["input"] == {"action": "goto", "url": "https://x.com/", "desc": "이동 · x.com/"}
    assert len(evs[1]["output"]) <= 200 and evs[1]["success"] is True  # 화면 기록에는 짧은 요약만


async def _false():
    return False

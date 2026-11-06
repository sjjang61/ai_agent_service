import asyncio
import json

from app.core.login_requests import PendingLogins
from app.services.browser_profile_service import _site, sanitize_state, summarize
from app.tools.browser_tools import DAEMON_SOURCE, DAEMON_VERSION, RequestUserLoginTool


def test_site_grouping():
    assert _site(".www.linkedin.com") == "linkedin.com"
    assert _site("accounts.google.com") == "google.com"
    assert _site("nid.naver.com") == "naver.com"
    assert _site("m.daum.net") == "daum.net"
    assert _site("foo.co.kr") == "foo.co.kr"


def test_sanitize_blocks_finance():
    state = {
        "cookies": [{"domain": ".linkedin.com"}, {"domain": ".paypal.com"}, {"domain": "www.kbstar.com"}],
        "origins": [{"origin": "https://www.paypal.com"}, {"origin": "https://www.naver.com"}],
    }
    clean = sanitize_state(state)
    assert [c["domain"] for c in clean["cookies"]] == [".linkedin.com"]
    assert [o["origin"] for o in clean["origins"]] == ["https://www.naver.com"]
    assert summarize(clean) == [{"domain": "linkedin.com", "cookies": 1}]


def test_daemon_source_compiles_and_version_matches():
    compile(DAEMON_SOURCE, "daemon", "exec")
    assert "VERSION = 9333, 900, 6" in DAEMON_SOURCE and DAEMON_VERSION == 6


def test_login_request_flow():
    async def run():
        tool = RequestUserLoginTool(user_id="u1", conversation_id="c1")
        task = asyncio.create_task(tool._arun("LinkedIn", "https://www.linkedin.com/login", "로그인 필요"))
        await asyncio.sleep(0.05)
        assert PendingLogins.get("c1", "u1")["site"] == "LinkedIn"
        assert PendingLogins.get("c1", "other") is None          # 남의 요청은 보이지 않는다
        assert not PendingLogins.resolve("c1", "other")
        assert PendingLogins.resolve("c1", "u1")
        assert json.loads(await task) == {"done": True}
        assert PendingLogins.get("c1", "u1") is None

    asyncio.run(run())


def test_login_tool_unavailable_when_disabled():
    out = json.loads(asyncio.run(RequestUserLoginTool(user_id="u", conversation_id="c", enabled=False)._arun("X")))
    assert out["unavailable"] is True


def test_looks_like_captcha():
    from app.tools.browser_tools import looks_like_captcha

    assert looks_like_captcha({"ok": True, "url": "https://www.skyscanner.co.kr/sttc/px/captcha-v2/index.html?url=x", "text": ""})
    assert looks_like_captcha({"ok": True, "url": "https://x.com/", "text": "Are you a person or a robot?\nPress & Hold"})
    assert looks_like_captcha({"ok": True, "url": "https://x.com/", "text": "자동 입력 방지 문자를 입력하세요"})
    assert not looks_like_captcha({"ok": True, "url": "https://x.com/search", "text": "항공권 검색 결과 " * 50})
    assert not looks_like_captcha({"ok": False, "error": "captcha"})


def test_browser_action_waits_for_user_on_captcha(monkeypatch):
    import asyncio

    from app.core.login_requests import PendingLogins
    from app.tools import browser_tools as bt

    calls = []

    async def fake_call(user_id, payload, timeout=90, sandbox_cid="", use_profile=True):
        calls.append(payload["cmd"])
        if payload["cmd"] == "goto":
            return {"ok": True, "url": "https://shop.test/captcha/1", "title": "t", "elements": [], "text": ""}
        return {"ok": True, "url": "https://shop.test/results", "title": "ok", "elements": [], "text": "results"}

    monkeypatch.setattr(bt, "browser_call", fake_call)

    async def run(login_enabled):
        tool = bt.BrowserActionTool(user_id="u1", conversation_id="c-cap", login_enabled=login_enabled)
        task = asyncio.create_task(tool._arun("goto", url="https://shop.test/"))
        await asyncio.sleep(0.05)
        if login_enabled:
            assert PendingLogins.get("c-cap", "u1")["site"] == "shop.test"
            PendingLogins.resolve("c-cap", "u1")
        return await task

    out = asyncio.run(run(True))
    assert "해결했습니다" in out and "results" in out and calls == ["goto", "snapshot"]
    calls.clear()
    out = asyncio.run(run(False))                      # 사용자 화면이 없는 실행은 기다리지 않는다
    assert "captcha" in out and calls == ["goto"]


def test_run_with_budget_excludes_user_wait():
    import asyncio

    from app.tools.browser_tools import WaitClock, run_with_budget

    async def go():
        clock = WaitClock()

        async def work():
            clock.waited += 0  # 사용자 대기를 시뮬레이션: 2.5초 중 2초는 대기
            await asyncio.sleep(2.5)
            return "ok"

        async def waiter():
            await asyncio.sleep(0.1)
            clock.waited = 2.0

        async def waiter():
            await asyncio.sleep(0.1)
            clock.waited = 2.0

        asyncio.ensure_future(waiter())
        assert await run_with_budget(work(), 1.0, clock) == "ok"       # 실제 작업 0.5초 < 1초

        # 지금 기다리는 중인 시간도 제외한다 (대기가 끝나기 전에 시간 초과되면 안 된다)
        from app.core.login_requests import PendingLogins

        c2 = WaitClock()

        async def long_wait_then_done():
            r = await c2.ask("c-budget", "u", {"site": "x"}, 30)
            return r

        async def resolver():
            await asyncio.sleep(2.2)
            PendingLogins.resolve("c-budget", "u")

        asyncio.ensure_future(resolver())
        assert await run_with_budget(long_wait_then_done(), 1.0, c2) == {"done": True}
        try:
            await run_with_budget(asyncio.sleep(5), 1.0, WaitClock())    # 대기 없이 5초 → 시간 초과
            assert False
        except asyncio.TimeoutError:
            pass

    asyncio.run(go())


def test_daemon_get_ping_reports_version():
    # browser_call 이 GET /ping 의 버전으로 이전 데몬을 판별한다. 버전이 빠지면 호출마다 브라우저가 재시작된다.
    from app.tools.browser_tools import DAEMON_SOURCE

    assert 'def do_GET(self): self._send({"ok": True, "v": VERSION})' in DAEMON_SOURCE

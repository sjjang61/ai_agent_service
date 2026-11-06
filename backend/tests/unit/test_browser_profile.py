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
    assert "VERSION = 9333, 900, 2" in DAEMON_SOURCE and DAEMON_VERSION == 2


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

"""크롬 확장 경로: 명령 왕복, 연결 끊김, 라우팅 우선순위, 확장 snap.js 동기화."""
import asyncio
import json
import pathlib

import pytest

from app.services import ext_browser, local_browser
from app.services.browser_snapshot import SNAP_JS


class FakeWS:
    def __init__(self, eb_holder, reply=None):
        self.sent = []
        self.holder = eb_holder
        self.reply = reply

    async def send_text(self, text):
        d = json.loads(text)
        self.sent.append(d)
        if self.reply is not None and "id" in d:
            asyncio.get_running_loop().call_soon(self.holder[0].on_message, {"id": d["id"], "result": self.reply})


@pytest.fixture(autouse=True)
def _clean():
    ext_browser._connections.clear()
    yield
    ext_browser._connections.clear()


def _make(reply=None):
    holder = []
    ws = FakeWS(holder, reply)
    eb = ext_browser.register("u1", ws)
    holder.append(eb)
    return eb, ws


@pytest.mark.asyncio
async def test_command_round_trip_and_unsupported_and_blocked():
    eb, ws = _make({"ok": True, "url": "https://www.coupang.com/", "elements": [], "text": "x"})
    res = await eb.handle({"cmd": "goto", "url": "https://www.coupang.com/"})
    assert res["ok"] and ws.sent[0]["cmd"] == "goto" and ws.sent[0]["id"] == 1
    assert (await eb.handle({"cmd": "drag", "ref": 1}))["ok"] is False  # 모르는 명령은 확장에 보내지 않는다
    assert len(ws.sent) == 1
    assert (await eb.handle({"cmd": "goto", "url": "file:///etc/passwd"}))["ok"] is False
    assert "blocked" in (await eb.handle({"cmd": "goto", "url": "http://127.0.0.1:8500/"}))["error"]


@pytest.mark.asyncio
async def test_disconnect_fails_pending_and_route_prefers_extension():
    eb, _ = _make(reply=None)
    task = asyncio.create_task(eb.handle({"cmd": "snapshot"}))
    await asyncio.sleep(0.05)
    eb.on_close()
    assert "연결이 끊어" in (await task)["error"]
    assert ext_browser.get_for("u1") is None  # 끊긴 연결은 쓰지 않는다
    eb2, _ = _make({"ok": True})
    assert await local_browser.route_for("u1") is None  # 로컬 Chrome 을 고르지 않았으면 확장이 붙어 있어도 쓰지 않는다 (기본)
    local_browser.request_extension(True)
    try:
        assert await local_browser.route_for("u1") is eb2  # 고른 요청만 확장으로
        assert await local_browser.route_for("u1", "sid-1") is eb2
        miss = await local_browser.route_for("other")  # 연결이 없으면 다른 브라우저로 우회하지 않고 이유를 알리는 오류
        assert miss is ext_browser.UNAVAILABLE and (await miss.handle({"cmd": "goto", "url": "https://a.com"}))["ok"] is False
        assert "연결되어 있지 않아" in (await miss.handle({"cmd": "snapshot"}))["error"] and (await miss.available()) is False
    finally:
        local_browser.request_extension(False)


def test_new_connection_replaces_old():
    old, _ = _make()
    new, _ = _make()
    assert old.connected is False and ext_browser.get_for("u1") is new


def test_extension_scripts_are_in_sync_with_server():
    import importlib.util

    root = pathlib.Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("export_snap_js", root / "backend" / "scripts" / "export_snap_js.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name, text in mod.render().items():
        assert (root / "chrome-extension" / name).read_text(encoding="utf-8") == text, f"{name} 이 서버 규칙과 다르다: backend/scripts/export_snap_js.py 를 다시 실행하세요"
    assert mod.render()["snap.js"] == SNAP_JS


@pytest.mark.asyncio
async def test_errors_are_mapped_stop_and_screenshot():
    import base64
    import os

    eb, ws = _make({"ok": False, "blocked": "그 자리에는 다른 요소(DIV x)가 있습니다."})
    r = await eb.handle({"cmd": "click", "ref": 7})
    assert r["ok"] is False and "ref 7" in r["error"] and "가려졌거나" in r["error"]
    eb2, _ = _make({"ok": False, "notfound": True})
    assert "찾을 수 없습니다" in (await eb2.handle({"cmd": "type", "ref": 3, "text": "a"}))["error"]
    eb3, ws3 = _make({"ok": True})
    eb3.on_message({"type": "stop"})  # 사용자가 확장에서 중지를 눌렀다
    assert "중지했습니다" in (await eb3.handle({"cmd": "click", "ref": 1, "run": "r1"}))["error"]
    assert "중지했습니다" in (await eb3.handle({"cmd": "snapshot", "run": "r1"}))["error"]  # 같은 작업은 계속 막는다
    assert (await eb3.handle({"cmd": "snapshot", "run": "r2"}))["ok"] is True  # 새 작업은 풀린다
    eb4, _ = _make({"ok": True, "img": base64.b64encode(b"PNG").decode(), "url": "https://a.com/"})
    shot = await eb4.handle({"cmd": "screenshot", "name": "t"})
    assert shot["ok"] and open(shot["path"], "rb").read() == b"PNG"
    os.remove(shot["path"])


def test_ext_token_is_rejected_by_regular_auth():
    from app.core.security import create_access_token, create_ext_token, decode_token

    assert decode_token(create_ext_token("u1"))["type"] == "ext"
    assert "type" not in decode_token(create_access_token("u1"))


@pytest.mark.asyncio
async def test_close_agent_tab_sends_close_and_respects_setting(monkeypatch):
    eb, ws = _make({"ok": True})
    await ext_browser.close_agent_tab("u1")
    assert ws.sent and ws.sent[-1]["cmd"] == "close_tab"
    n = len(ws.sent)
    monkeypatch.setattr(ext_browser.settings, "EXT_BROWSER_CLOSE_TAB", False)
    await ext_browser.close_agent_tab("u1")
    assert len(ws.sent) == n  # 끄면 보내지 않는다
    await ext_browser.close_agent_tab("nobody")  # 연결이 없으면 아무것도 하지 않는다

"""일반 크롬 확장(chrome-extension/)을 브라우저로 쓰는 경로.

사용자가 자기 크롬(전용 프로필 권장)에 확장을 설치하고 /ws/ext 로 접속하면, 이 사용자의 브라우저 작업을 그 크롬 탭에서 수행한다.
LocalBrowser(앱 브라우저·CDP)와 같은 명령/응답 규약(handle)을 따라서 도구·정책 계층은 그대로 쓴다.
확장은 CDP 를 쓰지 않고 탭 이동·스크립트 주입(SNAP_JS)·DOM 이벤트로만 조작한다.
"""
import asyncio
import json
import logging
from typing import Any, Optional
from urllib.parse import urlparse

from app.config import settings

logger = logging.getLogger(__name__)

COMMAND_TIMEOUT = 60.0
SUPPORTED = {"ping", "goto", "snapshot", "wait", "reload", "back", "scroll", "close", "export_state", "click", "type", "press", "select", "frame", "screenshot"}
STOP_MSG = "사용자가 브라우저 조작을 중지했습니다. 지금 즉시 멈추고, 여기까지의 진행 상황을 보고하세요. 같은 작업을 다시 시도하지 마세요."


class ExtensionBrowser:
    """접속한 확장 한 개. 명령은 하나씩 순서대로 처리한다."""

    def __init__(self, ws: Any, user_id: str):
        self.ws = ws
        self.user_id = user_id
        self.connected = True
        self._seq = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._lock = asyncio.Lock()
        self._stop_pending = False  # 사용자가 확장의 '중지'를 눌렀고 아직 처리하지 않았다
        self._stopped_run: Optional[str] = None
        self._shots = 0

    async def available(self) -> bool:
        return self.connected

    async def set_attention(self, message: str) -> None:
        try:
            await self.ws.send_text(json.dumps({"type": "attention", "message": message[:200]}))
        except Exception:  # noqa: BLE001
            pass

    async def reset_tabs(self) -> None:
        return None

    def on_message(self, data: dict) -> None:
        """확장이 보낸 응답({id, result})을 기다리는 호출에 전달한다."""
        if data.get("type") == "stop":
            self._stop_pending = True
            return
        fut = self._pending.pop(data.get("id"), None)
        if fut is not None and not fut.done():
            fut.set_result(data.get("result") or {"ok": False, "error": "빈 응답"})

    def on_close(self) -> None:
        self.connected = False
        for fut in self._pending.values():
            if not fut.done():
                fut.set_result({"ok": False, "error": "크롬 확장 연결이 끊어졌습니다. 확장이 켜져 있는지 확인하세요."})
        self._pending.clear()

    async def handle(self, c: dict) -> dict:
        cmd = c.get("cmd")
        if cmd == "ping":
            return {"ok": True, "v": 1, "extension": True}
        if cmd == "export_state":
            return {"ok": False, "error": "chrome extension keeps its own session"}
        if cmd == "close":
            return {"ok": True}  # 사용자의 브라우저는 닫지 않는다
        if cmd not in SUPPORTED:
            return {"ok": False, "error": f"크롬 확장은 아직 '{cmd}' 명령을 지원하지 않습니다"}
        if cmd == "goto":
            url = str(c.get("url", ""))
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return {"ok": False, "error": "http/https URL only"}
            from app.services.local_browser import _is_blocked_host

            host = parsed.hostname or ""
            if not settings.LOCAL_BROWSER_ALLOW_PRIVATE and await asyncio.get_running_loop().run_in_executor(None, _is_blocked_host, host):
                return {"ok": False, "error": f"blocked: private/internal address ({host})"}
        if not self.connected:
            return {"ok": False, "error": "크롬 확장이 연결되어 있지 않습니다"}
        run = c.get("run")
        if self._stop_pending:  # 사용자가 중지를 눌렀다: 그 시점의 작업(run 태그)은 더 조작하지 않는다
            self._stop_pending = False
            self._stopped_run = run or "-"
        if self._stopped_run is not None and (self._stopped_run == "-" or run == self._stopped_run):
            return {"ok": False, "error": STOP_MSG}
        self._stopped_run = None  # 새 작업이 시작되면 중지 상태를 푼다
        async with self._lock:
            self._seq += 1
            seq = self._seq
            fut: asyncio.Future = asyncio.get_running_loop().create_future()
            self._pending[seq] = fut
            try:
                await self.ws.send_text(json.dumps({"id": seq, **c}))
                return self._post(c, await asyncio.wait_for(fut, COMMAND_TIMEOUT))
            except asyncio.TimeoutError:
                self._pending.pop(seq, None)
                return {"ok": False, "error": "페이지가 응답하지 않습니다 (크롬 확장 응답 시간 초과). 같은 주소를 반복해 열지 마세요."}
            except Exception as e:  # noqa: BLE001
                self._pending.pop(seq, None)
                return {"ok": False, "error": f"크롬 확장 오류: {type(e).__name__}: {e}"[:400]}

    async def close_tab(self) -> None:
        """작업용 탭 닫기 (중지 상태와 무관하게 보낸다). 응답은 짧게만 기다린다."""
        if not self.connected:
            return
        async with self._lock:
            self._seq += 1
            fut: asyncio.Future = asyncio.get_running_loop().create_future()
            self._pending[self._seq] = fut
            try:
                await self.ws.send_text(json.dumps({"id": self._seq, "cmd": "close_tab"}))
                await asyncio.wait_for(fut, 5.0)
            except Exception:  # noqa: BLE001
                self._pending.pop(self._seq, None)

    def _post(self, c: dict, res: dict) -> dict:
        """확장의 응답을 LocalBrowser 와 같은 오류 문구·형식으로 맞춘다."""
        from app.services.browser_snapshot import BLOCKED_MSG

        ref = c.get("ref")
        if res.get("notfound"):
            return {"ok": False, "error": f"ref {ref} 요소를 찾을 수 없습니다. snapshot 으로 최신 ref 를 확인하세요"}
        if res.get("blocked"):
            return {"ok": False, "error": BLOCKED_MSG.format(ref=ref, what=res["blocked"])}
        if c.get("cmd") == "screenshot" and res.get("ok") and res.get("img"):  # 파일로 저장해 경로를 돌려준다 (LocalBrowser 와 같다)
            import base64
            import os
            import tempfile

            self._shots += 1
            name = "".join(ch for ch in str(c.get("name") or "shot") if ch.isalnum() or ch in "-_")[:40] or "shot"
            d = os.path.join(tempfile.gettempdir(), "agent_local_browser")
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, f"{name}-{self._shots}.png")
            with open(path, "wb") as f:
                f.write(base64.b64decode(res["img"]))
            return {"ok": True, "path": path, "url": res.get("url")}
        return res


async def close_agent_tab(user_id: str) -> None:
    """요청이 끝났을 때 확장이 작업용으로 연 탭을 닫는다. 다음 요청이 시작되면 새 탭을 연다."""
    if not settings.EXT_BROWSER_CLOSE_TAB:
        return
    eb = get_for(user_id)
    if eb is not None:
        await eb.close_tab()


class _Unavailable:
    """'로컬 Chrome 사용'을 골랐는데 확장이 연결돼 있지 않을 때의 자리표시자: 모든 명령이 이유를 알리는 오류로 끝난다."""

    MSG = ("Error: '로컬 Chrome 사용'이 선택됐지만 Chrome 확장이 연결되어 있지 않아 브라우저를 쓸 수 없습니다. "
           "다른 브라우저로 대신하지 말고, 사용자에게 '설정 > 브라우저 로그인 > 일반 Chrome 으로 조작'에서 확장을 설치·연결하거나 + 메뉴에서 로컬 Chrome 선택을 끄라고 안내하고 멈추세요.")

    async def available(self) -> bool:
        return False

    async def handle(self, c: dict) -> dict:
        if c.get("cmd") in ("ping", "close"):
            return {"ok": True}
        return {"ok": False, "error": self.MSG}

    async def set_attention(self, message: str) -> None:
        return None

    async def reset_tabs(self) -> None:
        return None


UNAVAILABLE = _Unavailable()
_connections: dict[str, ExtensionBrowser] = {}


def register(user_id: str, ws: Any) -> ExtensionBrowser:
    old = _connections.get(user_id)
    if old is not None:
        old.on_close()  # 같은 사용자의 새 접속이 이전 접속을 대신한다
    eb = ExtensionBrowser(ws, user_id)
    _connections[user_id] = eb
    logger.info("[ext] 크롬 확장 연결: user=%s", user_id)
    return eb


def unregister(user_id: str, eb: ExtensionBrowser) -> None:
    eb.on_close()
    if _connections.get(user_id) is eb:
        del _connections[user_id]
        logger.info("[ext] 크롬 확장 연결 종료: user=%s", user_id)


def get_for(user_id: str) -> Optional[ExtensionBrowser]:
    if not settings.EXT_BROWSER_ENABLED:
        return None
    eb = _connections.get(user_id)
    return eb if eb is not None and eb.connected else None

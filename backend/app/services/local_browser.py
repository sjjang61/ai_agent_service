"""로컬 브라우저: 데스크톱 앱(Electron)의 내장 브라우저를 CDP(Chrome DevTools Protocol)로 직접 조작한다.

sandbox 브라우저 데몬(browser_tools.DAEMON_SOURCE)과 같은 명령(goto/snapshot/click/type/...)과 같은 응답 형태를 제공해서,
`browser_call` 이 두 구현 중 하나로 보내기만 하면 에이전트 도구는 바뀌지 않는다.

Playwright 의 connect_over_cdp 는 Electron 에서 초기화가 멈추므로 쓰지 않고, 페이지 단위 CDP 웹소켓에 직접 연결한다.
조작할 페이지는 Electron 이 알려 주는 targetId(info 서버: CDP 포트 + 1)로 고른다 (UI 창과 구분하기 위함).
"""
import asyncio
import ipaddress
import json
import os
import socket
import tempfile
import time
import urllib.parse
import urllib.request
from typing import Any, Optional
from urllib.parse import urlparse

import websockets

from app.config import settings

from app.services.browser_snapshot import SNAP_JS  # sandbox 데몬과 같은 요소 수집 스크립트 (data-agent-ref 번호 부여)

# 키 이름 → (key, code, windowsVirtualKeyCode, text)
_KEYS: dict[str, tuple[str, str, int, str]] = {
    "Enter": ("Enter", "Enter", 13, "\r"),
    "Tab": ("Tab", "Tab", 9, ""),
    "Escape": ("Escape", "Escape", 27, ""),
    "Backspace": ("Backspace", "Backspace", 8, ""),
    "Delete": ("Delete", "Delete", 46, ""),
    "ArrowDown": ("ArrowDown", "ArrowDown", 40, ""),
    "ArrowUp": ("ArrowUp", "ArrowUp", 38, ""),
    "ArrowLeft": ("ArrowLeft", "ArrowLeft", 37, ""),
    "ArrowRight": ("ArrowRight", "ArrowRight", 39, ""),
    "PageDown": ("PageDown", "PageDown", 34, ""),
    "PageUp": ("PageUp", "PageUp", 33, ""),
    "Home": ("Home", "Home", 36, ""),
    "End": ("End", "End", 35, ""),
    "Space": (" ", "Space", 32, " "),
}


def key_spec(name: str) -> dict:
    """press 명령의 키 이름을 CDP Input.dispatchKeyEvent 인자로 바꾼다. 한 글자면 그 문자로 취급한다."""
    if name in _KEYS:
        key, code, vk, text = _KEYS[name]
    elif len(name) == 1:
        key, code, vk, text = name, ("Key" + name.upper() if name.isalpha() else name), ord(name.upper()), name
    else:
        raise ValueError(f"지원하지 않는 키입니다: {name}")
    spec = {"key": key, "code": code, "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk}
    if text:
        spec["text"] = text
    return spec


def _is_blocked_host(host: str) -> bool:
    try:
        return any(not ipaddress.ip_address(i[4][0]).is_global for i in socket.getaddrinfo(host, None))
    except Exception:
        return False


class LocalBrowserError(Exception):
    pass


class LocalBrowser:
    """데스크톱 앱 내장 브라우저 한 개를 조작한다. 명령은 하나씩 순서대로 처리한다."""

    def __init__(self, cdp_url: str, info_url: Optional[str] = None, sid: str = ""):
        self.sid = sid  # 비어 있으면 사용자가 보고 있는(활성) 탭, 있으면 그 병렬 세션 전용 탭
        self.cdp_url = cdp_url.rstrip("/")
        if info_url:
            self.info_url = info_url.rstrip("/")
        else:  # Electron 은 CDP 포트 + 1 에 info 서버를 연다
            u = urlparse(self.cdp_url)
            self.info_url = f"{u.scheme}://{u.hostname}:{(u.port or 9222) + 1}"
        self._ws: Any = None
        self._target_id: Optional[str] = None
        self._active_target: Optional[str] = None
        self._seq = 0
        self._lock = asyncio.Lock()
        self._shots = 0
        self._stopped_run: Optional[str] = None  # 사용자가 중지한 브라우저 작업(run 태그)
        self._seen_stop: Optional[int] = None  # 앱의 '중지' 누름 횟수 중 이미 처리한 값 (병렬 세션이 모두 중지되도록 횟수로 비교한다)

    # ── 연결 ──────────────────────────────────────────────────────────
    @staticmethod
    def _get_json(url: str, timeout: float = 3.0) -> Any:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 (로컬 loopback 주소만 쓴다)
            return json.loads(r.read())

    async def _find_ws_url(self) -> str:
        loop = asyncio.get_running_loop()
        q = f"?sid={urllib.parse.quote(self.sid)}" if self.sid else ""
        info = await loop.run_in_executor(None, self._get_json, f"{self.info_url}/agent-browser{q}")
        target_id = info["targetId"]
        tabs = await loop.run_in_executor(None, self._get_json, f"{self.cdp_url}/json")
        for t in tabs:
            if t.get("id") == target_id and t.get("webSocketDebuggerUrl"):
                self._target_id = target_id
                return t["webSocketDebuggerUrl"]
        raise LocalBrowserError("내장 브라우저 페이지를 찾을 수 없습니다")

    async def _reset_connection(self) -> None:
        ws, self._ws = self._ws, None
        if ws is not None:
            try:
                await ws.close()
            except Exception:  # noqa: BLE001
                pass

    async def _connect(self) -> None:
        if self._ws is not None and getattr(self._ws, "close_code", None) is None:
            return
        ws_url = await self._find_ws_url()
        self._ws = await websockets.connect(ws_url, max_size=32 * 1024 * 1024, open_timeout=5)
        await self._send("Page.enable")
        try:  # 사용자가 앱의 다른 곳을 보고 있어 브라우저 창에 포커스가 없어도 페이지가 포커스된 것으로 동작하게 한다
            # (포커스가 빠지는 순간 팝업·패널을 닫는 사이트에서 클릭으로 연 화면이 바로 닫히는 것을 막는다)
            await self._send("Emulation.setFocusEmulationEnabled", {"enabled": True})
        except LocalBrowserError:
            pass  # 지원하지 않는 브라우저 버전: 없어도 동작한다

    @staticmethod
    def _post_json(url: str, timeout: float = 2.0) -> Any:
        req = urllib.request.Request(url, data=b"{}", method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (로컬 loopback 주소만 쓴다)
            return json.loads(r.read())

    async def _activity(self) -> bool:
        """앱에 '에이전트가 조작 중'임을 알리고, 사용자가 중지를 눌렀는지(True) 돌려받는다. 앱과 통신이 안 되면 False."""
        try:
            res = await asyncio.get_running_loop().run_in_executor(None, self._post_body, f"{self.info_url}/activity", {"sid": self.sid})
            if not self.sid:
                self._active_target = res.get("targetId") or None  # 사용자가 보고 있는(활성) 탭 (병렬 세션은 자기 탭에 고정)
            if res.get("opened"):  # 접혀 있던 브라우저가 지금 펼쳐졌다: 화면 크기(viewport)가 잡힐 때까지 잠깐 기다린다
                await asyncio.sleep(0.6)
            seq = res.get("stopSeq")
            if seq is None:  # 구버전 앱: 한 번만 전달되는 stop 값
                return bool(res.get("stop"))
            seq = int(seq)
            prev, self._seen_stop = self._seen_stop, seq
            return prev is not None and seq > prev  # 처음 본 값은 기준으로만 삼는다
        except Exception:
            return False

    async def set_attention(self, message: str) -> None:
        """사용자가 직접 해야 할 일(로그인·CAPTCHA)이 있음을 앱에 알린다. 앱은 브라우저로 포커스를 옮기고 안내 배너를 보여 준다. 빈 문자열이면 해제."""
        try:
            await asyncio.get_running_loop().run_in_executor(None, self._post_body, f"{self.info_url}/attention", {"message": message[:200], "sid": self.sid})
        except Exception:
            pass  # 안내는 편의 기능이다

    @staticmethod
    def _post_body(url: str, body: dict, timeout: float = 2.0) -> Any:
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (로컬 loopback 주소만 쓴다)
            return json.loads(r.read())

    async def available(self) -> bool:
        try:
            async with self._lock:
                await self._connect()
            return True
        except Exception:
            self._ws = None
            return False

    async def _send(self, method: str, params: Optional[dict] = None, timeout: float = 30.0) -> dict:
        self._seq += 1
        mid = self._seq
        await self._ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        deadline = time.monotonic() + timeout
        while True:
            remain = deadline - time.monotonic()
            if remain <= 0:
                raise LocalBrowserError(f"CDP 응답 시간 초과: {method}")
            msg = json.loads(await asyncio.wait_for(self._ws.recv(), remain))
            if msg.get("id") == mid:
                if "error" in msg:
                    raise LocalBrowserError(f"{method}: {msg['error'].get('message', msg['error'])}")
                return msg.get("result", {})

    async def _eval(self, expression: str, timeout: float = 15.0) -> Any:
        res = await self._send(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
            timeout=timeout,
        )
        if "exceptionDetails" in res:
            d = res["exceptionDetails"]
            raise LocalBrowserError(d.get("exception", {}).get("description") or d.get("text", "script error"))
        return res.get("result", {}).get("value")

    # ── 페이지 상태 ───────────────────────────────────────────────────
    async def _settle(self, quiet: float = 3.0) -> None:
        """로드가 끝날 때까지 기다린다 (최대 quiet 초 추가 대기)."""
        end = time.monotonic() + 8.0
        while time.monotonic() < end:
            try:
                if await self._eval("document.readyState") in ("interactive", "complete"):
                    break
            except LocalBrowserError:
                pass  # 이동 중이라 실행 컨텍스트가 없는 순간
            await asyncio.sleep(0.15)
        end = time.monotonic() + quiet
        while time.monotonic() < end:
            try:
                if await self._eval("document.readyState") == "complete":
                    break
            except LocalBrowserError:
                pass
            await asyncio.sleep(0.15)

    async def _snapshot(self) -> dict:
        for attempt in (0, 1):  # 이동 직후엔 컨텍스트가 바뀌어 한 번 실패할 수 있다
            try:
                s = await self._eval(SNAP_JS)
                url = await self._eval("location.href")
                title = await self._eval("document.title")
                return {"url": url, "title": title, "elements": s["elements"], "text": s["text"], "sy": s.get("sy")}
            except LocalBrowserError:
                if attempt:
                    raise
                await asyncio.sleep(0.5)
        raise LocalBrowserError("snapshot 실패")

    # ── 입력 ──────────────────────────────────────────────────────────
    async def _element_center(self, ref: int) -> tuple[float, float]:
        js = (
            "(() => { const el = document.querySelector('[data-agent-ref=\"%d\"]'); if (!el) return null;"
            " el.scrollIntoView({block:'center', inline:'center'}); const r = el.getBoundingClientRect();"
            " return {x: r.x + r.width/2, y: r.y + r.height/2, w: r.width, h: r.height}; })()" % int(ref)
        )
        pos = await self._eval(js)
        if not pos:
            raise LocalBrowserError(f"ref {ref} 요소를 찾을 수 없습니다. snapshot 으로 최신 ref 를 확인하세요")
        return float(pos["x"]), float(pos["y"])

    async def _click_at(self, x: float, y: float) -> None:
        await self._send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        await self._send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
        await self._send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})

    async def _press(self, name: str) -> None:
        spec = key_spec(name)
        down = dict(spec, type="keyDown" if spec.get("text") else "rawKeyDown")
        await self._send("Input.dispatchKeyEvent", down)
        await self._send("Input.dispatchKeyEvent", dict(spec, type="keyUp"))

    # ── 명령 처리 ─────────────────────────────────────────────────────
    async def handle(self, c: dict) -> dict:
        """sandbox 데몬의 handle() 과 같은 명령/응답 규약."""
        cmd = c.get("cmd")
        try:
            async with self._lock:
                await self._connect()
                if cmd not in ("ping", "close", "export_state"):
                    run = c.get("run")
                    stopped = await self._activity()
                    if self._active_target and self._active_target != self._target_id:  # 탭이 바뀌었다: 활성 탭으로 다시 붙는다
                        await self._reset_connection()
                        await self._connect()
                    if stopped:  # 사용자가 앱에서 '중지'를 눌렀다
                        self._stopped_run = run or "-"
                    if self._stopped_run is not None and (self._stopped_run == "-" or run == self._stopped_run):
                        return {"ok": False, "error": "사용자가 브라우저 조작을 중지했습니다. 지금 즉시 멈추고, 여기까지의 진행 상황을 보고하세요. 같은 작업을 다시 시도하지 마세요."}
                    self._stopped_run = None  # 새 작업이 시작되면 중지 상태를 푼다
                return await self._dispatch(cmd, c)
        except LocalBrowserError as e:
            msg = str(e)
            if "시간 초과" in msg:  # 페이지가 멈췄거나 로딩이 끝나지 않는 경우: 원인을 알려 같은 주소를 반복하지 않게 한다
                msg = "페이지가 응답하지 않습니다 (로딩 시간 초과). 사이트나 네트워크 문제일 수 있으니 같은 주소를 반복해 열지 마세요."
            return {"ok": False, "error": msg[:400]}
        except asyncio.TimeoutError:
            return {"ok": False, "error": "페이지가 응답하지 않습니다 (로딩 시간 초과). 사이트나 네트워크 문제일 수 있으니 같은 주소를 반복해 열지 마세요."}
        except Exception as e:  # 연결 끊김 등
            self._ws = None
            return {"ok": False, "error": f"로컬 브라우저 오류: {type(e).__name__}: {e}"[:400]}

    async def _dispatch(self, cmd: Optional[str], c: dict) -> dict:
        if cmd == "ping":
            return {"ok": True, "v": 1, "local": True}
        if cmd == "export_state":  # 로그인 상태는 앱의 영구 세션에 남아 있으므로 서버 프로필로 저장하지 않는다
            return {"ok": False, "error": "local browser keeps its own session"}
        if cmd == "goto":
            url = str(c.get("url", ""))
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return {"ok": False, "error": "http/https URL only"}
            host = parsed.hostname or ""
            if not settings.LOCAL_BROWSER_ALLOW_PRIVATE and await asyncio.get_running_loop().run_in_executor(None, _is_blocked_host, host):
                return {"ok": False, "error": f"blocked: private/internal address ({host})"}
            res = await self._send("Page.navigate", {"url": url}, timeout=20.0)
            if res.get("errorText"):
                return {"ok": False, "error": f"이동 실패: {res['errorText']}"}
            await self._settle()
            return {"ok": True, **await self._snapshot()}
        if cmd == "snapshot":
            return {"ok": True, **await self._snapshot()}
        if cmd == "click":
            x, y = await self._element_center(int(c["ref"]))
            await self._click_at(x, y)
            await asyncio.sleep(0.6)
            await self._settle()
            return {"ok": True, **await self._snapshot()}
        if cmd == "type":
            ref, text = int(c["ref"]), str(c.get("text", ""))[:2000]
            focus = (
                "(() => { const el = document.querySelector('[data-agent-ref=\"%d\"]'); if (!el) return false;"
                " el.scrollIntoView({block:'center'}); el.focus();"
                " if (el.select) el.select(); else if (el.isContentEditable) document.execCommand('selectAll');"
                " return true; })()" % ref
            )
            if not await self._eval(focus):
                raise LocalBrowserError(f"ref {ref} 요소를 찾을 수 없습니다. snapshot 으로 최신 ref 를 확인하세요")
            if text:
                await self._send("Input.insertText", {"text": text})
            else:
                await self._press("Backspace")  # 선택된 내용 지우기
            if c.get("submit"):
                await self._press("Enter")
                await asyncio.sleep(0.6)
                await self._settle()
                return {"ok": True, **await self._snapshot()}
            return {"ok": True, "url": await self._eval("location.href")}
        if cmd == "select":
            ref, want = int(c["ref"]), json.dumps(str(c.get("text", "")))
            ok = await self._eval(
                "(() => { const el = document.querySelector('[data-agent-ref=\"%d\"]'); if (!el || !el.options) return false;"
                " const w = %s; const o = [...el.options].find(o => o.value === w || o.text.trim() === w);"
                " if (!o) return false; el.value = o.value;"
                " el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true})); return true; })()"
                % (ref, want)
            )
            if not ok:
                raise LocalBrowserError("선택할 수 있는 항목을 찾지 못했습니다")
            return {"ok": True}
        if cmd == "press":
            await self._press(str(c.get("key") or "Enter"))
            await asyncio.sleep(0.6)
            await self._settle()
            return {"ok": True, **await self._snapshot()}
        if cmd == "back":
            hist = await self._send("Page.getNavigationHistory")
            idx = hist["currentIndex"]
            if idx <= 0:
                return {"ok": False, "error": "이전 페이지가 없습니다"}
            await self._send("Page.navigateToHistoryEntry", {"entryId": hist["entries"][idx - 1]["id"]})
            await self._settle()
            return {"ok": True, **await self._snapshot()}
        if cmd == "reload":
            await self._send("Page.reload")
            await self._settle()
            return {"ok": True}
        if cmd == "scroll":
            js = {
                "down": "window.scrollBy(0, innerHeight*0.8)",
                "up": "window.scrollBy(0, -innerHeight*0.8)",
                "top": "window.scrollTo(0,0)",
                "bottom": "window.scrollTo(0, document.body.scrollHeight)",
            }.get(c.get("direction", "down"), "0")
            await self._eval(js)
            await asyncio.sleep(0.3)
            return {"ok": True, **await self._snapshot()}
        if cmd == "wait":
            await asyncio.sleep(min(float(c.get("seconds") or 1), 10))
            return {"ok": True, **await self._snapshot()}
        if cmd == "shot":  # sandbox 데몬과 같은 명령. 로컬 브라우저의 화면 저장은 도구(서버) 쪽이 frame 으로 한다
            return {"ok": True}
        if cmd == "frame":  # 현재 화면 JPEG (서버가 사용자의 sandbox 스크린샷 저장소에 남긴다)
            params: dict = {"format": "jpeg", "quality": int(c.get("quality") or 55)}
            clip = await self._page_clip()
            if clip:
                params["clip"] = clip
            res = await self._send("Page.captureScreenshot", params)
            return {"ok": True, "img": res["data"], "url": await self._eval("location.href"), "title": await self._eval("document.title")}
        if cmd == "screenshot":
            import base64

            res = await self._send("Page.captureScreenshot", {"format": "png"})
            self._shots += 1
            name = "".join(ch for ch in str(c.get("name") or "shot") if ch.isalnum() or ch in "-_")[:40] or "shot"
            d = os.path.join(tempfile.gettempdir(), "agent_local_browser")
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, f"{name}-{self._shots}.png")
            with open(path, "wb") as f:
                f.write(base64.b64decode(res["data"]))
            return {"ok": True, "path": path, "url": await self._eval("location.href")}
        if cmd == "close":
            return {"ok": True}  # 사용자의 브라우저는 닫지 않는다
        return {"ok": False, "error": "unknown cmd"}


    SHOT_MAX_WIDTH = 1600   # 스크린샷 가로 상한(px)
    SHOT_MAX_HEIGHT = 3000  # 스크린샷 세로 상한(px)

    async def _page_clip(self) -> Optional[dict]:
        """현재 보이는 영역을 페이지의 원래 폭(CSS 픽셀, 보통 1280px)으로 선명하게 캡처하기 위한 clip.

        앱의 브라우저는 페이지를 1280px 폭으로 배치한 뒤 창에 맞춰 축소(zoom, 예: 0.554)해 보여 준다. 기본 캡처는 그 축소된 화면 픽셀을
        그대로 저장해(예: 709px) 작은 글자가 뭉개진다. 이를 키우려면 clip 의 scale 을 올려야 하는데, 주의할 점이 있다:
        clip 의 좌표·크기 단위는 '축소 전 화면 단위'(= CSS 픽셀 × zoom)이지 CSS 픽셀이 아니다. CSS 크기(1280)로 지정하면 실제 보이는
        영역(약 700)을 넘어 내용은 그대로이고 배경만 넓어진다. 그래서 보이는 영역을 zoom 으로 환산해 지정한다.
        scale 은 결과 가로가 CSS 폭(페이지 원래 폭)이 되도록 정하되, 기본 캡처보다 작아지지 않게(Retina 처럼 이미 크면 그대로) 하고 상한을 둔다.
        스크롤 위치(pageX/pageY)도 같은 단위로 환산한다. 측정이 안 되면 None(기본 캡처)."""
        try:
            m = await self._send("Page.getLayoutMetrics")
            vp = m.get("cssVisualViewport") or m.get("visualViewport") or {}
            css_w, css_h = float(vp.get("clientWidth") or 0), float(vp.get("clientHeight") or 0)
            if css_w < 2 or css_h < 2:
                return None
            zoom = float((m.get("visualViewport") or {}).get("zoom") or 1) or 1.0
            dpr = float(await self._eval("window.devicePixelRatio") or zoom)
            dsf = max(dpr / zoom, 0.5)  # 화면 배율(Retina 2 등). devicePixelRatio = zoom × 화면 배율
            w, h = css_w * zoom, css_h * zoom  # 보이는 영역 (clip 단위)
            base_w, base_h = w * dsf, h * dsf  # 기본 캡처의 결과 크기(px)
            target_w = min(max(css_w, base_w), self.SHOT_MAX_WIDTH)
            scale = min(target_w / base_w, self.SHOT_MAX_HEIGHT / base_h)
            return {"x": float(vp.get("pageX") or 0) * zoom, "y": float(vp.get("pageY") or 0) * zoom, "width": w, "height": h, "scale": scale}
        except (LocalBrowserError, TypeError, ValueError):
            return None

    async def reset_tabs(self) -> None:
        """앱의 브라우저 탭을 모두 닫고 새 탭 하나로 시작한다 (새 요청의 시작). 이 연결도 새 탭에 다시 붙는다."""
        await asyncio.get_running_loop().run_in_executor(None, self._post_body, f"{self.info_url}/tabs/reset", {}, 5.0)
        await self._reset_connection()
        self._target_id = None
        self._active_target = None

    async def open_session(self) -> None:
        """병렬 작업용 전용 탭을 앱에 만든다 (앱이 동시 세션 수를 제한한다)."""
        res = await asyncio.get_running_loop().run_in_executor(None, self._post_body, f"{self.info_url}/tabs", {"sid": self.sid}, 5.0)
        if not res.get("ok"):
            raise LocalBrowserError(str(res.get("error") or "병렬 브라우저 탭을 만들지 못했습니다"))

    async def close_session(self) -> None:
        self._ws, ws = None, self._ws
        if ws is not None:
            try:
                await ws.close()
            except Exception:  # noqa: BLE001
                pass
        try:
            await asyncio.get_running_loop().run_in_executor(None, self._post_body, f"{self.info_url}/tabs/close", {"sid": self.sid})
        except Exception:  # noqa: BLE001
            pass  # 탭 정리는 앱이 유휴 탭을 따로 닫는다


_instance: Optional[LocalBrowser] = None
_sessions: dict[str, LocalBrowser] = {}  # 병렬 세션 id → 그 세션 전용 연결


def get_local_browser() -> Optional[LocalBrowser]:
    """설정이 켜져 있으면 공용 인스턴스를, 아니면 None."""
    global _instance
    if not settings.LOCAL_BROWSER_CDP_URL or not settings.LOCAL_BROWSER_USER_ID:
        return None
    if _instance is None or _instance.cdp_url != settings.LOCAL_BROWSER_CDP_URL.rstrip("/"):
        _instance = LocalBrowser(settings.LOCAL_BROWSER_CDP_URL)
    return _instance


async def route_for(user_id: str, sid: str = "") -> Optional[LocalBrowser]:
    """이 사용자의 브라우저 작업을 로컬 브라우저로 보낼 수 있으면 그 인스턴스를, 아니면 None(→ sandbox).
    sid 가 있으면 open_session_for 로 만든 병렬 세션 전용 연결을 돌려준다."""
    if user_id != settings.LOCAL_BROWSER_USER_ID:
        return None
    if sid:
        lb = _sessions.get(sid)
        return lb if lb is not None and await lb.available() else None
    lb = get_local_browser()
    if lb is not None and await lb.available():
        return lb
    return None


async def open_session_for(user_id: str, sid: str) -> Optional[LocalBrowser]:
    """병렬 작업용 전용 탭을 만들고 연결한다. 로컬 브라우저를 쓸 수 없으면 None, 탭 수 제한 등으로 실패하면 LocalBrowserError."""
    base = await route_for(user_id)
    if base is None:
        return None
    lb = LocalBrowser(base.cdp_url, base.info_url, sid=sid)
    await lb.open_session()
    _sessions[sid] = lb
    if not await lb.available():
        await close_session_for(sid)
        raise LocalBrowserError("병렬 브라우저 탭에 연결하지 못했습니다")
    return lb


_fresh_users: set[str] = set()  # 새 요청이 시작됐지만 아직 브라우저를 쓰지 않은 사용자
_reset_lock = asyncio.Lock()


def mark_new_turn(user_id: str) -> None:
    """사용자의 새 요청이 시작됐다. 이 요청에서 브라우저를 처음 쓸 때 열려 있던 탭을 모두 닫는다 (브라우저를 안 쓰는 요청은 탭을 건드리지 않는다)."""
    if settings.LOCAL_BROWSER_CDP_URL and user_id == settings.LOCAL_BROWSER_USER_ID:
        _fresh_users.add(user_id)
        from app.tools.browser_tools import clear_handoff

        clear_handoff(user_id)  # 새 요청에서는 탭을 닫고 시작하므로 이전 요청의 화면을 이어받지 않는다


async def reset_if_new_turn(user_id: str) -> None:
    """새 요청의 첫 브라우저 사용 직전에 한 번만 탭을 정리한다. 동시에 들어온 호출은 정리가 끝날 때까지 기다린다."""
    if user_id not in _fresh_users:
        return
    async with _reset_lock:
        if user_id not in _fresh_users:
            return  # 앞선 호출이 이미 정리했다
        _fresh_users.discard(user_id)
        lb = await route_for(user_id)
        if lb is not None:
            try:
                await lb.reset_tabs()
                _sessions.clear()
            except Exception:  # noqa: BLE001
                pass  # 정리 실패는 작업을 막지 않는다 (구버전 앱 등)


async def close_session_for(sid: str) -> None:
    lb = _sessions.pop(sid, None)
    if lb is not None:
        await lb.close_session()

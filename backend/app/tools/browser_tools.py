"""cli_browser_agent: sandbox 안의 실제(헤드리스 Chromium) 브라우저를 조작해 로그인·클릭·폼 입력 같은 상호작용 작업을 수행한다.

구성
  - sandbox 안에서 Playwright 브라우저 데몬(127.0.0.1:9333)이 떠 있으면서 세션(쿠키/로그인 상태)을 유지한다.
  - BrowserActionTool: 데몬에 명령(goto/snapshot/click/type/...)을 보내는 저수준 도구 (내부 에이전트 전용).
  - CliBrowserAgentTool: 위 도구를 가진 내부 에이전트(LLM)를 돌려 작업(task)을 끝까지 수행하고 결과만 보고한다.
브라우저는 호스트가 아니라 sandbox 컨테이너 안에서 실행되고, 사설망/루프백으로 가는 요청은 데몬이 차단한다.
"""
import asyncio
import json
import re
import uuid
import shlex
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool

from app.agent.prompts import sections
from app.config import settings

DAEMON_PATH = "/tmp/_browser_daemon.py"
STATE_PATH = "/tmp/_browser_state.json"  # 저장된 로그인 상태. 데몬이 읽자마자 지운다
DAEMON_PORT = 9333
DAEMON_VERSION = 6
LOGIN_TIMEOUT_SECONDS = 600

DAEMON_SOURCE = r'''
import base64, ipaddress, json, os, socket, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

PORT, IDLE_SECONDS, VERSION = 9333, 900, 6
STATE_PATH = "/tmp/_browser_state.json"
SHOT_DIR = "/workspace/browser"

SNAP_JS = """() => {
  const sel = 'a[href],button,input,select,textarea,summary,[role=button],[role=link],[role=checkbox],[role=tab],[role=menuitem],[onclick]';
  document.querySelectorAll('[data-agent-ref]').forEach(e => e.removeAttribute('data-agent-ref'));
  const out = []; let n = 0;
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect(); const st = getComputedStyle(el);
    if (r.width < 2 || r.height < 2 || st.visibility === 'hidden' || st.display === 'none' || el.type === 'hidden') continue;
    n++; el.setAttribute('data-agent-ref', String(n));
    const label = (el.innerText || el.value || el.getAttribute('aria-label') || el.placeholder || el.title || el.alt || '').trim().replace(/\\s+/g, ' ').slice(0, 80);
    const item = {ref: n, tag: el.tagName.toLowerCase(), label};
    if (el.type && el.tagName !== 'BUTTON' && el.tagName !== 'A') item.type = el.type;
    if (el.getAttribute('role')) item.role = el.getAttribute('role');
    if (el.name) item.name = el.name;
    if (el.placeholder) item.placeholder = el.placeholder;
    if (el.value && el.type !== 'password' && el.tagName !== 'BUTTON') item.value = String(el.value).slice(0, 60);
    if (el.href) item.href = el.href.slice(0, 120);
    if (el.checked) item.checked = true;
    if (el.disabled) item.disabled = true;
    out.push(item);
    if (n >= 120) break;
  }
  return {elements: out, text: (document.body.innerText || '').slice(0, 3000)};
}"""

FOCUS_JS = """() => {
  const el = document.activeElement;
  if (!el || el === document.body) return null;
  const t = (el.type || '').toLowerCase();
  const editable = el.tagName === 'TEXTAREA' || el.isContentEditable || el.tagName === 'IFRAME' ||
    (el.tagName === 'INPUT' && !['button','submit','checkbox','radio','reset','image','file','range','color'].includes(t));
  if (!editable) return null;
  const r = el.getBoundingClientRect();
  if (r.width < 2 || r.height < 2) return null;
  return {x: r.x, y: r.y, w: r.width, h: r.height, password: t === 'password'};
}"""

_cache = {}
def blocked(host):
    if host in _cache:
        return _cache[host]
    try:
        bad = any(not ipaddress.ip_address(i[4][0]).is_global for i in socket.getaddrinfo(host, None))
    except Exception:
        bad = False
    _cache[host] = bad
    return bad

def route(r):
    u = urlparse(r.request.url)
    if u.scheme in ("http", "https") and u.hostname and blocked(u.hostname):
        return r.abort("blockedbyclient")
    r.continue_()

pw = sync_playwright().start()
browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
_ctx_args = dict(viewport={"width": 1280, "height": 800}, locale="ko-KR")
if os.path.exists(STATE_PATH):   # 사용자 로그인 상태(쿠키/localStorage) 복원 후 파일은 바로 지운다
    try:
        ctx = browser.new_context(storage_state=STATE_PATH, **_ctx_args)
    except Exception:
        ctx = browser.new_context(**_ctx_args)
    try: os.remove(STATE_PATH)
    except Exception: pass
else:
    ctx = browser.new_context(**_ctx_args)
ctx.route("**/*", route)
state = {"page": ctx.new_page(), "shots": 0}
ctx.on("page", lambda p: state.update(page=p))          # 새 탭이 열리면 그쪽으로 전환
state["page"].on("dialog", lambda d: d.accept())

def fresh_page():
    old = state["page"]
    p = ctx.new_page()
    state["page"] = p
    p.on("dialog", lambda d: d.accept())
    try: old.close()
    except Exception: pass
    return p

SHOTS_DIR = SHOT_DIR + "/shots"

def shot(page, run):
    """작업 진행 화면용 스크린샷(JPEG)을 남기고 index.jsonl 에 기록한다. 실패해도 작업에는 영향이 없다."""
    try:
        os.makedirs(SHOTS_DIR, exist_ok=True)
        ts = int(time.time() * 1000)
        path = "%s/%d.jpg" % (SHOTS_DIR, ts)
        page.screenshot(path=path, type="jpeg", quality=55)
        with open(SHOTS_DIR + "/index.jsonl", "a") as f:
            f.write(json.dumps({"f": path, "url": page.url, "title": page.title(), "t": ts, "run": run}, ensure_ascii=False) + "\n")
        files = sorted(x for x in os.listdir(SHOTS_DIR) if x.endswith(".jpg"))
        for old in files[:-60]:
            os.remove(SHOTS_DIR + "/" + old)
    except Exception:
        pass

def settle(page):
    try: page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception: pass
    try: page.wait_for_load_state("networkidle", timeout=3000)
    except Exception: pass

def snapshot(page):
    s = page.evaluate(SNAP_JS)
    return {"url": page.url, "title": page.title(), "elements": s["elements"], "text": s["text"]}

def handle(c):
    page = state["page"]
    cmd = c.get("cmd")
    if cmd == "ping": return {"ok": True, "v": VERSION}
    if cmd == "export_state": return {"ok": True, "state": ctx.storage_state()}
    if cmd == "frame":
        raw = page.screenshot(type="jpeg", quality=int(c.get("quality") or 55))
        try: focus = page.evaluate(FOCUS_JS)
        except Exception: focus = None
        return {"ok": True, "img": base64.b64encode(raw).decode(), "url": page.url, "title": page.title(), "focus": focus}
    if cmd == "mouse":   # 사용자의 직접 조작 (로그인 화면)
        x, y = float(c["x"]), float(c["y"])
        page.mouse.click(x, y, button=c.get("button") or "left", click_count=int(c.get("count") or 1))
        time.sleep(0.3); return {"ok": True}
    if cmd == "mousedown":   # 길게 누르기(캡차 등)를 위해 누름과 뗌을 따로 보낸다
        page.mouse.move(float(c["x"]), float(c["y"]))
        page.mouse.down(button=c.get("button") or "left", click_count=int(c.get("count") or 1)); return {"ok": True}
    if cmd == "mouseup":
        page.mouse.up(button=c.get("button") or "left", click_count=int(c.get("count") or 1)); return {"ok": True}
    if cmd == "wheel":
        page.mouse.move(float(c.get("x") or 640), float(c.get("y") or 400))
        page.mouse.wheel(0, float(c.get("dy") or 0)); return {"ok": True}
    if cmd == "insert":
        page.keyboard.insert_text(str(c.get("text", ""))[:2000]); return {"ok": True}
    if cmd == "keypress":
        page.keyboard.press(str(c.get("key", "Enter"))); time.sleep(0.2); return {"ok": True}
    if cmd == "reload":
        page.reload(wait_until="domcontentloaded", timeout=20000); return {"ok": True}
    if cmd == "goto":
        url = str(c.get("url", ""))
        if urlparse(url).scheme not in ("http", "https"): return {"ok": False, "error": "http/https URL only"}
        host = urlparse(url).hostname or ""
        if blocked(host):  # 내부/사설 주소는 이동하기 전에 거부 (오류 페이지를 남기지 않는다)
            return {"ok": False, "error": "blocked: private/internal address (%s)" % host}
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            fresh_page()  # 실패한 이동(리다이렉트 차단 등)은 오류 페이지가 다음 이동을 방해하므로 새 탭으로 교체
            raise
        settle(page)
        shot(state["page"], c.get("run"))
        return {"ok": True, **snapshot(state["page"])}
    if cmd == "snapshot": return {"ok": True, **snapshot(page)}
    loc = lambda: page.locator('[data-agent-ref="%s"]' % int(c["ref"])).first
    if cmd == "click":
        loc().click(timeout=8000); time.sleep(0.6); settle(state["page"])
        shot(state["page"], c.get("run"))
        return {"ok": True, **snapshot(state["page"])}
    if cmd == "type":
        loc().fill(str(c.get("text", ""))[:2000], timeout=8000)
        if c.get("submit"):
            page.keyboard.press("Enter"); time.sleep(0.6); settle(state["page"])
            shot(state["page"], c.get("run"))
            return {"ok": True, **snapshot(state["page"])}
        return {"ok": True, "url": page.url}
    if cmd == "select":
        loc().select_option(str(c.get("text", "")), timeout=8000); return {"ok": True}
    if cmd == "press":
        page.keyboard.press(str(c.get("key", "Enter"))); time.sleep(0.6); settle(state["page"])
        shot(state["page"], c.get("run"))
        return {"ok": True, **snapshot(state["page"])}
    if cmd == "back":
        page.go_back(wait_until="domcontentloaded", timeout=15000); settle(page)
        shot(state["page"], c.get("run"))
        return {"ok": True, **snapshot(state["page"])}
    if cmd == "scroll":
        d = c.get("direction", "down")
        js = {"down": "window.scrollBy(0, innerHeight*0.8)", "up": "window.scrollBy(0, -innerHeight*0.8)",
              "top": "window.scrollTo(0,0)", "bottom": "window.scrollTo(0, document.body.scrollHeight)"}.get(d, "0")
        page.evaluate(js); time.sleep(0.3)
        return {"ok": True, **snapshot(page)}
    if cmd == "wait":
        time.sleep(min(float(c.get("seconds", 1)), 10)); return {"ok": True, **snapshot(page)}
    if cmd == "screenshot":
        os.makedirs(SHOT_DIR, exist_ok=True); state["shots"] += 1
        name = "".join(ch for ch in str(c.get("name") or "shot") if ch.isalnum() or ch in "-_")[:40] or "shot"
        path = "%s/%s-%d.png" % (SHOT_DIR, name, state["shots"])
        page.screenshot(path=path); return {"ok": True, "path": path, "url": page.url}
    if cmd == "close":
        os._exit(0)
    return {"ok": False, "error": "unknown cmd"}

last = [time.time()]
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def do_GET(self): self._send({"ok": True, "v": VERSION})
    def do_POST(self):
        last[0] = time.time()
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            self._send(handle(body))
        except Exception as e:
            self._send({"ok": False, "error": (type(e).__name__ + ": " + str(e))[:400]})
        last[0] = time.time()

srv = HTTPServer(("127.0.0.1", PORT), H); srv.timeout = 30
while time.time() - last[0] < IDLE_SECONDS:
    srv.handle_request()
browser.close(); pw.stop()
'''


def _truncate(s: str, limit: int) -> str:
    return s if len(s) <= limit else s[:limit] + f"...[{len(s) - limit} chars truncated]"


_start_locks: dict[str, asyncio.Lock] = {}


def _start_lock(cid: str) -> asyncio.Lock:
    return _start_locks.setdefault(cid, asyncio.Lock())


async def _daemon_up(cid: str) -> bool:
    from app.services.sandbox_service import sandbox_manager

    code, _, _ = await sandbox_manager.exec_command(cid, f"curl -sf -m 2 http://127.0.0.1:{DAEMON_PORT}/ping >/dev/null", timeout=15)
    return code == 0


async def _daemon_version(cid: str) -> Optional[int]:
    """떠 있는 데몬의 버전. 데몬이 없으면 None, 버전 정보가 없는 아주 오래된 데몬은 0."""
    from app.services.sandbox_service import sandbox_manager

    _, out, _ = await sandbox_manager.exec_command(cid, f"curl -sf -m 2 http://127.0.0.1:{DAEMON_PORT}/ping", timeout=15)
    try:
        return int(json.loads(out).get("v", 0))
    except (ValueError, TypeError, AttributeError):
        return None


async def browser_call(user_id: str, payload: dict, timeout: int = 90, sandbox_cid: str = "", use_profile: bool = True) -> dict:
    """sandbox 의 브라우저 데몬에 명령을 보내고 결과(dict)를 받는다. 데몬이 없으면 시작한다.
    데몬을 새로 시작할 때 사용자의 저장된 로그인 상태(프로필)를 넣어 준다 (use_profile=False 면 깨끗한 세션)."""
    from app.services.browser_profile_service import BrowserProfileService
    from app.services.sandbox_service import sandbox_manager
    from app.tools.workspace_tools import _container

    cid = await _container(user_id, sandbox_cid)
    url = f"http://127.0.0.1:{DAEMON_PORT}"
    if payload.get("cmd") != "close":
        # 같은 컨테이너에서 데몬이 동시에 두 번 시작되면(포트 충돌) 하나가 죽고 로그인 상태 복원도 어긋나므로 시작 구간을 직렬화한다
        async with _start_lock(cid):
            await sandbox_manager.write_file(cid, DAEMON_PATH, DAEMON_SOURCE.encode("utf-8"))
            ver = await _daemon_version(cid)
            if ver is not None and ver != DAEMON_VERSION:
                # 앱을 업데이트하기 전에 시작된 데몬은 새 기능(스크린샷, 프로필 등)이 없으므로 종료하고 다시 시작한다
                await daemon_post(cid, {"cmd": "close"}, timeout=5)
                for _ in range(10):
                    await asyncio.sleep(0.5)
                    if await _daemon_version(cid) is None:
                        break
            if await _daemon_version(cid) is None:
                if use_profile:
                    state = await BrowserProfileService.load_state(user_id)
                    if state:
                        await sandbox_manager.write_file(cid, STATE_PATH, state.encode("utf-8"))
                start = (
                    f"nohup python3 {DAEMON_PATH} >/tmp/_browser_daemon.log 2>&1 </dev/null & "
                    f"for i in $(seq 1 60); do curl -sf -m 1 {url}/ping >/dev/null && break; sleep 0.5; done"
                )
                await sandbox_manager.exec_command(cid, start, timeout=60)
            up = await _daemon_up(cid)
        if not up:
            _, log, _ = await sandbox_manager.exec_command(cid, "tail -c 600 /tmp/_browser_daemon.log 2>/dev/null", timeout=10)
            detail = log.strip()
            hint = ""
            if "Executable doesn't exist" in detail or "playwright install" in detail:
                hint = " (sandbox 이미지에 non-root 사용자가 실행할 수 있는 Chromium 이 필요합니다. sandbox-image 를 다시 빌드하세요)"
            elif "ENOSPC" in detail:
                hint = " (디스크 공간이 부족합니다)"
            return {"ok": False, "error": "브라우저를 시작하지 못했습니다: " + _truncate(detail[-400:], 400) + hint}
    cmd = f"curl -s -m {timeout} -X POST -d {shlex.quote(json.dumps(payload, ensure_ascii=False))} {url}/cmd"
    _, out, err = await sandbox_manager.exec_command(cid, cmd, timeout=timeout + 40)
    if not out.strip():
        return {"ok": False, "error": "브라우저 응답이 없습니다: " + _truncate(err.strip(), 300)} if payload.get("cmd") != "close" else {"ok": True}
    try:
        return json.loads(out)
    except ValueError:
        return {"ok": False, "error": _truncate(out.strip(), 300)}


async def daemon_post(cid: str, payload: dict, timeout: int = 30) -> dict:
    """이미 떠 있는 데몬에 명령만 보낸다 (시작·소스 쓰기 없음). 실시간 화면 조작처럼 잦은 호출용."""
    from app.services.sandbox_service import sandbox_manager

    cmd = f"curl -s -m {timeout} -X POST -d {shlex.quote(json.dumps(payload, ensure_ascii=False))} http://127.0.0.1:{DAEMON_PORT}/cmd"
    _, out, _ = await sandbox_manager.exec_command(cid, cmd, timeout=timeout + 15)
    try:
        return json.loads(out)
    except ValueError:
        return {"ok": False, "error": _truncate(out.strip(), 200) or "no response"}


async def persist_profile(user_id: str, sandbox_cid: str = "") -> Optional[list]:
    """실행 중인 브라우저의 로그인 상태를 사용자 프로필로 저장한다. 데몬이 없으면 아무것도 하지 않는다(None)."""
    from app.services.browser_profile_service import BrowserProfileService
    from app.tools.workspace_tools import _container

    cid = await _container(user_id, sandbox_cid)
    if not await _daemon_up(cid):
        return None
    res = await daemon_post(cid, {"cmd": "export_state"}, timeout=20)
    if not res.get("ok") or not isinstance(res.get("state"), dict):
        return None
    st = res["state"]
    if not st.get("cookies") and not st.get("origins"):
        return []  # 빈 세션(새 세션 등)이 저장된 프로필을 지우지 않게 한다
    return await BrowserProfileService.save_state(user_id, st)


def _format(res: dict) -> str:
    if not res.get("ok"):
        return f"Error: {res.get('error', 'unknown error')}"
    parts = [f"URL: {res['url']}"] if res.get("url") else []
    if res.get("title"):
        parts.append(f"Title: {res['title']}")
    if res.get("path"):
        parts.append(f"Screenshot saved: {res['path']}")
    if "elements" in res:
        parts.append("Interactive elements (use `ref` with click/type/select; refs change after every snapshot):")
        parts += [json.dumps(e, ensure_ascii=False) for e in res["elements"]]
        parts.append("Page text:\n" + _truncate(res.get("text", ""), 3000))
    return "\n".join(parts) if parts else "OK"


class WaitClock:
    """사용자의 응답(로그인·CAPTCHA 해결)을 기다린 시간. 브라우저 작업의 제한 시간에서 뺀다."""

    def __init__(self) -> None:
        self.waited = 0.0
        self._since: Optional[float] = None  # 지금 기다리는 중이면 시작 시각

    def total(self) -> float:
        """끝난 대기 + 지금 기다리는 중인 시간"""
        now = asyncio.get_running_loop().time()
        return self.waited + (now - self._since if self._since is not None else 0.0)

    async def ask(self, conversation_id: str, user_id: str, info: dict, timeout: float) -> dict:
        from app.core.login_requests import PendingLogins

        self._since = asyncio.get_running_loop().time()
        try:
            return await PendingLogins.ask(conversation_id, user_id, info, timeout)
        finally:
            self.waited = self.total()
            self._since = None


async def run_with_budget(coro, budget: float, clock: WaitClock):
    """사용자를 기다린 시간(clock.waited)을 뺀 실제 작업 시간이 budget 을 넘으면 TimeoutError."""
    task = asyncio.ensure_future(coro)
    start = asyncio.get_running_loop().time()
    try:
        while not task.done():
            await asyncio.wait({task}, timeout=1)
            if asyncio.get_running_loop().time() - start - clock.total() > budget:
                raise asyncio.TimeoutError
        return task.result()
    finally:
        if not task.done():
            task.cancel()


_CAPTCHA_URL = re.compile(r"captcha|/px/|recaptcha|hcaptcha|challenge-platform|/cdn-cgi/challenge", re.I)
_CAPTCHA_TEXT = re.compile(
    r"are you a (person|human) or a robot|press (&|and) hold|press and hold|verify (that )?you('re| are) (a )?human|"
    r"i'?m not a robot|prove you('re| are) (a )?human|로봇이 아닙니다|사람인지 확인|보안 문자|캡차|자동 입력 방지|버튼을 (길게|꾹) ?누",
    re.I,
)


def looks_like_captcha(res: dict) -> bool:
    """페이지 이동 결과가 CAPTCHA·봇 확인 화면으로 보이는지 (주소 또는 화면 앞부분의 문구)."""
    if not res.get("ok"):
        return False
    if _CAPTCHA_URL.search(str(res.get("url", ""))):
        return True
    return bool(_CAPTCHA_TEXT.search(str(res.get("text", ""))[:1500] + " " + str(res.get("title", ""))))


class BrowserActionInput(BaseModel):
    action: Literal["goto", "snapshot", "click", "type", "select", "press", "scroll", "back", "screenshot", "wait"] = Field(
        description="goto(url) | snapshot | click(ref) | type(ref,text,submit) | select(ref,text=option) | press(key) | scroll(direction) | back | screenshot(text=name) | wait(seconds)"
    )
    url: Optional[str] = Field(default=None, description="For goto: http(s) URL")
    ref: Optional[int] = Field(default=None, description="Element ref from the latest snapshot (click/type/select)")
    text: Optional[str] = Field(default=None, description="Text to type, option to select, or screenshot name")
    key: Optional[str] = Field(default=None, description="For press: key such as Enter, Tab, Escape, ArrowDown")
    direction: Optional[Literal["down", "up", "top", "bottom"]] = Field(default=None, description="For scroll")
    submit: bool = Field(default=False, description="For type: press Enter after typing")
    seconds: Optional[float] = Field(default=None, description="For wait: seconds (max 10)")


class BrowserActionTool(BaseTool):
    """내부 에이전트 전용 저수준 브라우저 조작 도구."""
    name: str = "browser_action"
    description: str = (
        "Control a real browser. Typical loop: goto -> read the snapshot (interactive elements with refs + page text) -> "
        "click/type/select/press using refs -> read the new snapshot. Refs are only valid for the latest snapshot."
    )
    args_schema: type[BaseModel] = BrowserActionInput
    user_id: str = ""
    sandbox_cid: str = ""  # 비어 있으면 사용자 공용 sandbox
    use_profile: bool = True
    conversation_id: str = ""  # 보안 확인(CAPTCHA) 때 사용자에게 브라우저를 열어 줄 대화방
    login_enabled: bool = False
    clock: Any = None
    run_tag: str = ""  # 한 번의 브라우저 작업(cli_browser_agent 호출) 식별자. 스크린샷을 이 작업에 묶는다

    def _run(self, *args, **kwargs) -> str:
        return "This tool supports async execution only"

    async def _arun(self, action: str, url: Optional[str] = None, ref: Optional[int] = None, text: Optional[str] = None,
                    key: Optional[str] = None, direction: Optional[str] = None, submit: bool = False,
                    seconds: Optional[float] = None) -> str:
        payload = {"cmd": action, "url": url, "ref": ref, "text": text, "key": key,
                   "direction": direction, "submit": submit, "seconds": seconds, "name": text, "run": self.run_tag or None}
        try:
            res = await browser_call(self.user_id, {k: v for k, v in payload.items() if v is not None}, sandbox_cid=self.sandbox_cid, use_profile=self.use_profile)
            note = ""
            if self.login_enabled and self.conversation_id and looks_like_captcha(res):
                res, note = await self._let_user_solve(res)
            return note + _format(res)
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"

    async def _let_user_solve(self, res: dict) -> tuple[dict, str]:
        """CAPTCHA·봇 확인 화면이면 에이전트가 우회하지 않고, 채팅에 브라우저 열기 카드를 띄워 사용자가 직접 해결할 때까지 기다린다."""
        from urllib.parse import urlparse

        url = str(res.get("url", ""))
        host = (urlparse(url).hostname or "사이트").removeprefix("www.")
        for attempt in range(2):
            info = {"site": host[:80], "url": url[:500], "reason": "CAPTCHA(로봇 확인) 화면이 나타났습니다. 열린 브라우저에서 직접 해결해 주세요."}
            result = await (self.clock or WaitClock()).ask(self.conversation_id, self.user_id, info, LOGIN_TIMEOUT_SECONDS)
            if not result.get("done"):
                why = "취소했습니다" if result.get("cancelled") else "시간이 초과되었습니다"
                return res, f"[사용자가 CAPTCHA 해결을 {why}. 우회하지 말고 이 사실을 보고하고 멈추세요.]\n"
            res = await browser_call(self.user_id, {"cmd": "snapshot"}, sandbox_cid=self.sandbox_cid, use_profile=self.use_profile)
            if not looks_like_captcha(res):
                return res, "[사용자가 CAPTCHA 를 해결했습니다. 아래는 해결 후 화면입니다. 이어서 작업하세요.]\n"
            url = str(res.get("url", url))
        return res, "[CAPTCHA 가 아직 남아 있습니다. 해결되지 않았다고 보고하고 멈추세요.]\n"


class RequestLoginInput(BaseModel):
    site: str = Field(description="Site name the user must sign in to, e.g. 'LinkedIn'")
    url: Optional[str] = Field(default=None, description="Login page URL (optional)")
    reason: Optional[str] = Field(default=None, description="One short sentence on why the login is needed")


class RequestUserLoginTool(BaseTool):
    """로그인이 필요한 화면을 만났을 때 사용자가 직접 로그인하도록 요청하고 완료를 기다린다."""
    name: str = "request_user_login"
    description: str = (
        "Ask the USER to sign in themselves when the page needs a login (login form, authwall, 2FA, CAPTCHA). "
        "A live browser opens for the user; execution PAUSES until they finish (or cancel, or 10 minutes pass). "
        "Never ask for or type the user's password yourself. After it returns {\"done\": true}, take a fresh snapshot "
        "and continue; the session is already logged in."
    )
    args_schema: type[BaseModel] = RequestLoginInput
    user_id: str = ""
    conversation_id: str = ""
    enabled: bool = True
    clock: Any = None

    def _run(self, *args, **kwargs) -> str:
        return "This tool supports async execution only"

    async def _arun(self, site: str, url: Optional[str] = None, reason: Optional[str] = None) -> str:
        if not self.enabled or not self.conversation_id:
            return json.dumps(
                {"unavailable": True, "message": "No interactive screen is available. Stop and tell the user in your report "
                 f"that {site} needs a login which they can do in the web app (Customize > 브라우저 로그인), then ask again."},
                ensure_ascii=False,
            )
        info = {"site": site[:80], "url": (url or "")[:500], "reason": (reason or "")[:200]}
        result = await (self.clock or WaitClock()).ask(self.conversation_id, self.user_id, info, LOGIN_TIMEOUT_SECONDS)
        return json.dumps(result, ensure_ascii=False)


BROWSER_INSTRUCTIONS = sections("browser_agent")  # prompts/browser_agent.md


class CliBrowserAgentInput(BaseModel):
    task: str = Field(description="Full description of what to do in the browser, including any credentials or data the user provided")
    start_url: Optional[str] = Field(default=None, description="URL to open first (optional)")
    new_session: bool = Field(default=False, description="Restart the browser with a clean session (drops cookies/login state)")


class CliBrowserAgentTool(BaseTool):
    name: str = "cli_browser_agent"
    description: str = (
        "Perform tasks that need interacting with a real website in a browser: logging in, clicking buttons, filling and "
        "submitting forms, multi-page flows, pages that need JavaScript. A browser sub-agent does the whole task and reports "
        "the result (login state persists between calls). For simply reading a page or searching, use web_search/web_crawler instead."
    )
    args_schema: type[BaseModel] = CliBrowserAgentInput
    user_id: str = ""
    sandbox_cid: str = ""  # 비어 있으면 사용자 공용 sandbox
    conversation_id: str = ""  # 로그인 요청 카드를 띄울 대화방
    login_enabled: bool = True  # 예약·메신저 실행처럼 사용자 화면이 없으면 False
    llm_provider: str = ""
    model: Optional[str] = None

    def _run(self, *args, **kwargs) -> str:
        return "This tool supports async execution only"

    async def _arun(self, task: str, start_url: Optional[str] = None, new_session: bool = False) -> str:
        try:
            from agno.agent import Agent

            from app.agent.agno_engine import build_agno_model, to_agno_function

            if new_session:
                try:
                    await browser_call(self.user_id, {"cmd": "close"}, timeout=10, sandbox_cid=self.sandbox_cid)
                except Exception:
                    pass
                await asyncio.sleep(1)
            profile = not new_session  # 새 세션은 저장된 로그인 상태 없이 시작하고, 끝나도 프로필을 덮어쓰지 않는다
            run = uuid.uuid4().hex[:8]
            clock = WaitClock()
            browser_tool = BrowserActionTool(
                user_id=self.user_id, sandbox_cid=self.sandbox_cid, use_profile=profile, run_tag=run,
                conversation_id=self.conversation_id, login_enabled=self.login_enabled, clock=clock,
            )
            login_tool = RequestUserLoginTool(user_id=self.user_id, conversation_id=self.conversation_id, enabled=self.login_enabled, clock=clock)
            agent = Agent(
                name="BrowserAgent",
                model=build_agno_model(self.llm_provider or settings.LLM_TYPE, self.model),
                tools=[to_agno_function(browser_tool), to_agno_function(login_tool)],
                tool_call_limit=settings.BROWSER_MAX_STEPS,
                instructions=BROWSER_INSTRUCTIONS,
            )
            prompt = task if not start_url else f"{task}\n\n(시작 URL: {start_url})"
            try:
                out = await run_with_budget(agent.arun(prompt), settings.BROWSER_TIMEOUT_SECONDS, clock)
            finally:
                if profile:  # 이번 작업에서 로그인된 사이트가 다음 대화·sandbox 에서도 유지되도록 저장
                    try:
                        await persist_profile(self.user_id, self.sandbox_cid)
                    except Exception:
                        pass
            text = str(getattr(out, "content", "") or "").strip()
            text = text[:15000] if text else "(browser agent returned no result)"
            return f"{text}\n\n[browser_run:{run}]"
        except asyncio.TimeoutError:
            return f"Error: browser task timed out after {settings.BROWSER_TIMEOUT_SECONDS}s"
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"

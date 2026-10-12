"""cli_browser_agent: sandbox 안의 실제(헤드리스 Chromium) 브라우저를 조작해 로그인·클릭·폼 입력 같은 상호작용 작업을 수행한다.

구성
  - sandbox 안에서 Playwright 브라우저 데몬(127.0.0.1:9333)이 떠 있으면서 세션(쿠키/로그인 상태)을 유지한다.
  - BrowserActionTool: 데몬에 명령(goto/snapshot/click/type/...)을 보내는 저수준 도구 (내부 에이전트 전용).
  - CliBrowserAgentTool: 위 도구를 가진 내부 에이전트(LLM)를 돌려 작업(task)을 끝까지 수행하고 결과만 보고한다.
브라우저는 호스트가 아니라 sandbox 컨테이너 안에서 실행되고, 사설망/루프백으로 가는 요청은 데몬이 차단한다.
"""
import asyncio
import json
import shlex
from typing import Literal, Optional

from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool

from app.config import settings

DAEMON_PATH = "/tmp/_browser_daemon.py"
DAEMON_PORT = 9333

DAEMON_SOURCE = r'''
import ipaddress, json, os, socket, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

PORT, IDLE_SECONDS = 9333, 900
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
ctx = browser.new_context(viewport={"width": 1280, "height": 800}, locale="ko-KR")
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
    if cmd == "ping": return {"ok": True}
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
        return {"ok": True, **snapshot(state["page"])}
    if cmd == "snapshot": return {"ok": True, **snapshot(page)}
    loc = lambda: page.locator('[data-agent-ref="%s"]' % int(c["ref"])).first
    if cmd == "click":
        loc().click(timeout=8000); time.sleep(0.6); settle(state["page"])
        return {"ok": True, **snapshot(state["page"])}
    if cmd == "type":
        loc().fill(str(c.get("text", ""))[:2000], timeout=8000)
        if c.get("submit"):
            page.keyboard.press("Enter"); time.sleep(0.6); settle(state["page"])
            return {"ok": True, **snapshot(state["page"])}
        return {"ok": True, "url": page.url}
    if cmd == "select":
        loc().select_option(str(c.get("text", "")), timeout=8000); return {"ok": True}
    if cmd == "press":
        page.keyboard.press(str(c.get("key", "Enter"))); time.sleep(0.6); settle(state["page"])
        return {"ok": True, **snapshot(state["page"])}
    if cmd == "back":
        page.go_back(wait_until="domcontentloaded", timeout=15000); settle(page)
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
    def do_GET(self): self._send({"ok": True})
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


async def browser_call(user_id: str, payload: dict, timeout: int = 90) -> dict:
    """sandbox 의 브라우저 데몬에 명령을 보내고 결과(dict)를 받는다. 데몬이 없으면 시작한다."""
    from app.services.sandbox_service import sandbox_manager
    from app.tools.workspace_tools import _container

    cid = await _container(user_id)
    url = f"http://127.0.0.1:{DAEMON_PORT}"
    if payload.get("cmd") != "close":
        await sandbox_manager.write_file(cid, DAEMON_PATH, DAEMON_SOURCE.encode("utf-8"))
    ensure = (
        f"curl -sf -m 2 {url}/ping >/dev/null || ("
        f"nohup python3 {DAEMON_PATH} >/tmp/_browser_daemon.log 2>&1 </dev/null & "
        f"for i in $(seq 1 60); do curl -sf -m 1 {url}/ping >/dev/null && break; sleep 0.5; done)"
    )
    cmd = f"{ensure}; curl -s -m {timeout} -X POST -d {shlex.quote(json.dumps(payload, ensure_ascii=False))} {url}/cmd"
    code, out, err = await sandbox_manager.exec_command(cid, cmd, timeout=timeout + 40)
    if not out.strip():
        _, log, _ = await sandbox_manager.exec_command(cid, "tail -c 600 /tmp/_browser_daemon.log 2>/dev/null", timeout=10)
        detail = (log or err).strip()
        hint = ""
        if "Executable doesn't exist" in detail or "playwright install" in detail:
            hint = " (sandbox 이미지에 non-root 사용자가 실행할 수 있는 Chromium 이 필요합니다. sandbox-image 를 다시 빌드하세요)"
        elif "ENOSPC" in detail:
            hint = " (디스크 공간이 부족합니다)"
        return {"ok": False, "error": "브라우저를 시작하지 못했습니다: " + _truncate(detail[-400:], 400) + hint}
    try:
        return json.loads(out)
    except ValueError:
        return {"ok": False, "error": _truncate(out.strip(), 300)}


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

    def _run(self, *args, **kwargs) -> str:
        return "This tool supports async execution only"

    async def _arun(self, action: str, url: Optional[str] = None, ref: Optional[int] = None, text: Optional[str] = None,
                    key: Optional[str] = None, direction: Optional[str] = None, submit: bool = False,
                    seconds: Optional[float] = None) -> str:
        payload = {"cmd": action, "url": url, "ref": ref, "text": text, "key": key,
                   "direction": direction, "submit": submit, "seconds": seconds, "name": text}
        try:
            return _format(await browser_call(self.user_id, {k: v for k, v in payload.items() if v is not None}))
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"


BROWSER_INSTRUCTIONS = [
    "당신은 실제 브라우저를 조작해 작업을 끝까지 수행하는 에이전트입니다. browser_action 도구로만 브라우저를 제어합니다.",
    "작업 순서: goto → snapshot(요소 목록과 페이지 텍스트 확인) → click/type/select/press → 새 snapshot 확인. ref 는 가장 최근 snapshot 의 것만 유효합니다.",
    "사용자가 작업에 명시한 계정 정보만 사용하고 임의로 만들어내지 마세요. 입력 후에는 결과 화면으로 성공 여부를 반드시 확인하세요.",
    "CAPTCHA·2단계 인증·결제/삭제처럼 되돌릴 수 없는 동작이 필요하면(작업에 명시적으로 지시되지 않은 경우) 진행하지 말고 상황을 보고하고 멈추세요.",
    "같은 동작을 반복해도 진척이 없으면 다른 방법을 시도하고, 그래도 안 되면 막힌 지점을 보고하세요.",
    "끝나면 한국어로 간결히 보고하세요: 수행한 단계, 최종 URL, 추출한 정보(원문 그대로), 저장한 스크린샷 경로.",
]


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
                    await browser_call(self.user_id, {"cmd": "close"}, timeout=10)
                except Exception:
                    pass
                await asyncio.sleep(1)
            agent = Agent(
                name="BrowserAgent",
                model=build_agno_model(self.llm_provider or settings.LLM_TYPE, self.model),
                tools=[to_agno_function(BrowserActionTool(user_id=self.user_id))],
                tool_call_limit=settings.BROWSER_MAX_STEPS,
                instructions=BROWSER_INSTRUCTIONS,
            )
            prompt = task if not start_url else f"{task}\n\n(시작 URL: {start_url})"
            out = await asyncio.wait_for(agent.arun(prompt), timeout=settings.BROWSER_TIMEOUT_SECONDS)
            text = str(getattr(out, "content", "") or "").strip()
            return text[:15000] if text else "(browser agent returned no result)"
        except asyncio.TimeoutError:
            return f"Error: browser task timed out after {settings.BROWSER_TIMEOUT_SECONDS}s"
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"

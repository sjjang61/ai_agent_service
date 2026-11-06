"""웹앱 게이트웨이: 프록시 리스너의 ASGI 앱 (HTTP 스트리밍, SSE, WebSocket).

두 가지 모드가 있다.
- port   : 비공개 앱마다 열리는 20000번대 포트. 소유자만 접속 — 메인 앱이 발급한 일회용 실행 티켓(?t=)을 세션 쿠키로 바꿔 인증한다.
- public : App Store 에 공개(승인)된 앱. 포트 하나에서 Host 헤더({slug}.도메인)로 앱을 구분하고 익명 접속을 허용한다 (요청률·깨우기 횟수 제한).

앱 컨테이너가 꺼져 있으면 깨운 뒤(HTML 은 로딩 페이지, 그 외는 최대 APP_WAKE_WAIT_SECONDS 대기) 컨테이너의 loopback 게시 포트로 포워딩한다.
업스트림 주소는 서버가 아는 값만 쓴다.
"""
import asyncio
import logging
from typing import Optional
from urllib.parse import urlencode

import httpx
import websockets
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from app.config import settings
from app.services import app_auth
from app.services.app_policy import RateLimiter, host_slug

logger = logging.getLogger(__name__)

STATUS_PATH = "/__app/status"
SESSION_COOKIE = "appsess_"
REVIEW_COOKIE = "appreview"
HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade"}

_client: Optional[httpx.AsyncClient] = None
_req_limiter = RateLimiter(settings.APP_PUBLIC_RATE_PER_MIN)
_wake_limiter = RateLimiter(settings.APP_PUBLIC_WAKE_PER_MIN)


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=600.0), follow_redirects=False,
                                    limits=httpx.Limits(max_connections=200, max_keepalive_connections=50))
    return _client


def _cookie_name(st) -> str:
    return f"{SESSION_COOKIE}{st.port}"


_PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
body{{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8f9fa;color:#333}}
.box{{text-align:center;max-width:560px;padding:24px}}.sp{{width:34px;height:34px;border:3px solid #e0e0e0;border-top-color:#333;border-radius:50%;animation:s .8s linear infinite;margin:0 auto 16px}}
@keyframes s{{to{{transform:rotate(360deg)}}}}pre{{text-align:left;background:#f1f3f5;padding:12px;border-radius:8px;font-size:12px;white-space:pre-wrap;word-break:break-all;max-height:240px;overflow:auto}}
#m{{font-size:14px;color:#666}}h1{{font-size:18px}}</style></head><body><div class="box">{body}</div>{script}</body></html>"""

_LOADING = _PAGE.format(
    title="앱을 시작하는 중...",
    body='<div class="sp"></div><p id="m">앱을 시작하는 중입니다. 잠시만 기다려 주세요...</p>',
    script="""<script>(async()=>{for(let i=0;i<120;i++){await new Promise(r=>setTimeout(r,1500));try{const r=await fetch('%s',{credentials:'same-origin'});
const d=await r.json();if(d.ready){location.reload();return}if(d.status==='failed'){document.querySelector('.box').innerHTML='<h1>앱을 시작하지 못했습니다</h1><pre></pre>';
document.querySelector('pre').textContent=d.message||'';return}document.getElementById('m').textContent=d.message||'시작하는 중...'}catch(e){}}
document.getElementById('m').textContent='시작 시간이 초과되었습니다. 새로고침해 주세요.'})()</script>""" % STATUS_PATH,
)


def _error_page(title: str, message: str, status: int) -> HTMLResponse:
    import html

    return HTMLResponse(_PAGE.format(title=html.escape(title), body=f"<h1>{html.escape(title)}</h1><pre>{html.escape(message)}</pre>", script=""), status_code=status)


def _wants_html(request: Request) -> bool:
    return request.method == "GET" and "text/html" in request.headers.get("accept", "")


def _fwd_headers(request: Request, st) -> dict:
    h = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP and k.lower() not in ("host", "cookie")}
    # 소유자·검수자 세션 쿠키(appsess_*, appreview)는 어떤 앱에도 넘기지 않는다 (같은 호스트의 다른 포트 앱이 받을 수 있다)
    cookies = "; ".join(c.strip() for c in request.headers.get("cookie", "").split(";") if c.strip() and not c.strip().startswith((SESSION_COOKIE, REVIEW_COOKIE + "=")))
    if cookies:
        h["cookie"] = cookies
    h["host"] = f"localhost:{st.container_port}"  # vite preview 등의 allowedHosts 검사를 통과하도록 업스트림 기준 호스트
    h["x-forwarded-host"] = request.headers.get("host", "")
    h["x-forwarded-proto"] = request.url.scheme
    h["x-forwarded-for"] = (request.headers.get("x-forwarded-for", "") + ", " if request.headers.get("x-forwarded-for") else "") + (request.client.host if request.client else "")
    return h


def _rewrite_location(loc: str, request: Request, st) -> str:
    origin = f"{request.url.scheme}://{request.headers.get('host', '')}"
    for base in (f"http://localhost:{st.container_port}", f"http://127.0.0.1:{st.container_port}", f"http://127.0.0.1:{st.upstream}"):
        if loc.startswith(base):
            return origin + loc[len(base):]
    return loc


def _strip_token(request) -> str:
    """실행 티켓(t)은 앱에 넘기지 않는다."""
    return urlencode([(k, v) for k, v in request.query_params.multi_items() if k != "t"])


def make_gateway(host, app_id: Optional[str], mode: str = "port") -> Starlette:
    def resolve(scope_headers_host: str, app_id=app_id):
        if mode == "port":
            return host.states.get(app_id)
        slug = host_slug(scope_headers_host)
        return host.by_slug(slug) if slug else None

    def try_wake(st) -> Optional[asyncio.Task]:
        t = host._wake.get(st.id)
        if t and not t.done():
            return t  # 이미 시작 중이면 합류 (횟수 제한에 포함하지 않는다)
        if mode == "public" and not _wake_limiter.allow(st.id):
            return None
        return host.wake(st.id)

    async def ready_upstream(st, wait: bool) -> Optional[int]:
        if st.status == "running" and st.upstream:
            return st.upstream
        task = try_wake(st)
        if wait and task:
            try:
                await asyncio.wait_for(asyncio.shield(task), settings.APP_WAKE_WAIT_SECONDS)
            except (asyncio.TimeoutError, Exception):  # noqa: BLE001
                pass
        return st.upstream if st.status == "running" else None

    def check_access(st, query_t: Optional[str], cookies: dict, client_ip: str) -> tuple:
        """(허용 여부, 거부 응답 또는 None, 세션 쿠키로 바꿔야 할 티켓이 유효한지). WebSocket 에서도 쓴다."""
        if mode == "public":
            if not host.public_ok(st):
                # 검수자 미리보기: 승인 전·정지된 앱도 검수 티켓/세션이 있으면 열어 볼 수 있다
                if app_auth.check_review_session(cookies.get(REVIEW_COOKIE), st.id):
                    return True, None, False
                if query_t and app_auth.check_review_ticket(query_t, st.id):
                    return True, None, "review"
                return False, _error_page("공개되지 않은 앱입니다", "이 앱은 공개되지 않았거나 공개가 중단되었습니다.", 404), False
            if not _req_limiter.allow((client_ip, st.id)):
                return False, Response("요청이 너무 많습니다. 잠시 후 다시 시도하세요.", status_code=429, headers={"Retry-After": "30"}), False
            return True, None, False
        if app_auth.check_session(cookies.get(_cookie_name(st)), st.id, st.user_id, st.epoch):
            return True, None, False
        if query_t and app_auth.check_ticket(query_t, st.id, st.user_id):
            return True, None, True
        return False, _error_page("비공개 앱입니다", "이 앱은 소유자만 열 수 있습니다. 서비스의 My Apps 에서 '실행'으로 여세요.", 401), False

    async def authorize(request: Request, st) -> Optional[Response]:
        ok, denied, ticket = check_access(st, request.query_params.get("t"), request.cookies, request.client.host if request.client else "")
        if not ok:
            return denied
        if ticket:  # 티켓 → 세션 쿠키로 교환하고 티켓 없는 주소로 이동
            q = _strip_token(request)
            resp = RedirectResponse(request.url.path + (f"?{q}" if q else ""), status_code=303)
            if ticket == "review":
                resp.set_cookie(REVIEW_COOKIE, app_auth.make_review_session(st.id), httponly=True, samesite="lax", path="/", max_age=3600)
            else:
                resp.set_cookie(_cookie_name(st), app_auth.make_session(st.id, st.user_id, st.epoch), httponly=True, samesite="lax", path="/", max_age=app_auth.SESSION_TTL)
            return resp
        return None

    async def status(request: Request):
        st = resolve(request.headers.get("host", ""))
        if not st:
            return JSONResponse({"status": "missing", "ready": False, "message": "앱을 찾을 수 없습니다"}, status_code=404)
        ok, denied, _ = check_access(st, None, request.cookies, request.client.host if request.client else "")
        if not ok:
            return JSONResponse({"detail": "denied"}, status_code=denied.status_code if denied else 403)
        if st.status == "stopped":
            try_wake(st)
        msg = host.cooldown_message(st) or {"starting": "앱을 시작하는 중...", "stopped": "앱을 깨우는 중...", "running": "준비되었습니다", "failed": st.error or "실패"}.get(st.status, "")
        return JSONResponse({"status": st.status, "ready": st.status == "running", "message": msg})

    async def proxy(request: Request):
        st = resolve(request.headers.get("host", ""))
        if not st:
            return _error_page("앱을 찾을 수 없습니다", "존재하지 않거나 삭제된 앱입니다.", 404)
        denied = await authorize(request, st)
        if denied is not None:
            return denied
        host.touch(st)
        wants_html = _wants_html(request)
        up = await ready_upstream(st, wait=not wants_html)
        if up is None:
            note = host.cooldown_message(st)
            if wants_html:
                if note or st.status == "failed":
                    return _error_page("앱을 시작하지 못했습니다", note or st.error or "", 503)
                return HTMLResponse(_LOADING, status_code=503, headers={"Retry-After": "3", "Cache-Control": "no-store"})
            return JSONResponse({"error": "app_starting" if st.status != "failed" else "app_failed", "message": note or st.error or "앱을 시작하는 중입니다. 잠시 후 다시 시도하세요."},
                                status_code=503, headers={"Retry-After": "3"})
        q = _strip_token(request)
        url = f"http://127.0.0.1:{up}{request.url.path}" + (f"?{q}" if q else "")
        try:
            req = _http().build_request(request.method, url, headers=_fwd_headers(request, st), content=request.stream())
            resp = await _http().send(req, stream=True)
        except httpx.ConnectError:
            await _upstream_lost(st)
            return _error_page("앱에 연결하지 못했습니다", "앱이 종료되었을 수 있습니다. 잠시 후 새로고침하면 다시 시작합니다.", 502)
        except httpx.TimeoutException:
            return Response("앱 응답 시간이 초과되었습니다", status_code=504)
        except httpx.HTTPError as e:
            if isinstance(e, httpx.RemoteProtocolError):
                await _upstream_lost(st)
            return Response(f"프록시 오류: {type(e).__name__}", status_code=502)
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in HOP_BY_HOP}
        if "location" in headers:
            headers["location"] = _rewrite_location(headers["location"], request, st)
        if mode == "public":
            headers.setdefault("x-content-type-options", "nosniff")
        return StreamingResponse(resp.aiter_raw(), status_code=resp.status_code, headers=headers, background=BackgroundTask(resp.aclose))

    async def _upstream_lost(st):
        if st.container_id and not await host._manager().is_running(st.container_id):
            st.status, st.upstream, st.container_id = "stopped", None, None
            await host._persist(st.id, status="stopped", container_id=None)

    async def ws_proxy(ws: WebSocket):
        st = resolve(ws.headers.get("host", ""))
        if not st:
            await ws.close(code=4404)
            return
        ok, _, _ = check_access(st, None, ws.cookies, ws.client.host if ws.client else "")
        if not ok:
            await ws.close(code=4401)
            return
        host.touch(st)
        up = await ready_upstream(st, wait=True)
        if up is None:
            await ws.close(code=1013, reason="app not ready")
            return
        protos = [p.strip() for p in ws.headers.get("sec-websocket-protocol", "").split(",") if p.strip()]
        query = _strip_token(ws)
        url = f"ws://127.0.0.1:{up}{ws.url.path}" + (f"?{query}" if query else "")
        try:
            async with websockets.connect(url, subprotocols=protos or None, additional_headers={"Host": f"localhost:{st.container_port}"}, max_size=None) as upstream:
                await ws.accept(subprotocol=upstream.subprotocol)
                await _relay(ws, upstream)
        except Exception as e:  # noqa: BLE001
            logger.debug("[apps] websocket 프록시 종료 (%s): %s", st.name, e)
            if ws.client_state in (WebSocketState.CONNECTING, WebSocketState.CONNECTED):
                await ws.close(code=1011)

    async def _relay(ws: WebSocket, upstream):
        async def c2u():
            try:
                while True:
                    msg = await ws.receive()
                    if msg["type"] == "websocket.disconnect":
                        break
                    if msg.get("text") is not None:
                        await upstream.send(msg["text"])
                    elif msg.get("bytes") is not None:
                        await upstream.send(msg["bytes"])
            except WebSocketDisconnect:
                pass
            finally:
                await upstream.close()

        async def u2c():
            try:
                async for m in upstream:
                    if ws.client_state != WebSocketState.CONNECTED:
                        break
                    await (ws.send_text(m) if isinstance(m, str) else ws.send_bytes(m))
            except Exception:  # noqa: BLE001
                pass

        tasks = [asyncio.create_task(c2u()), asyncio.create_task(u2c())]
        _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()

    methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
    return Starlette(routes=[
        Route(STATUS_PATH, status, methods=["GET"]),
        WebSocketRoute("/{path:path}", ws_proxy),
        Route("/{path:path}", proxy, methods=methods),
    ])

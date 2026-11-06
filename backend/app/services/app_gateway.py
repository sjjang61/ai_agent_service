"""웹앱 게이트웨이: 앱마다 하나씩 열리는 프록시 리스너(20000번대)의 ASGI 앱.

요청을 받으면 접근 토큰을 확인하고, 앱 컨테이너가 꺼져 있으면 깨운 뒤(HTML 은 로딩 페이지, 그 외는 최대 APP_WAKE_WAIT_SECONDS 대기),
컨테이너의 loopback 게시 포트로 스트리밍 포워딩한다 (HTTP, SSE, WebSocket). 업스트림 주소는 서버가 아는 값만 쓴다.
"""
import asyncio
import hmac
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

logger = logging.getLogger(__name__)

STATUS_PATH = "/__app/status"
HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade"}

_client: Optional[httpx.AsyncClient] = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=600.0), follow_redirects=False,
                                    limits=httpx.Limits(max_connections=200, max_keepalive_connections=50))
    return _client


def token_ok(st, query_token: Optional[str], cookie_token: Optional[str], header_token: Optional[str] = None) -> bool:
    """접근 토큰이 필요 없는 앱이면 항상 True. 필요하면 쿼리·쿠키·헤더 중 하나가 맞아야 한다 (상수 시간 비교)."""
    if not st.require_token:
        return True
    return any(t and hmac.compare_digest(t, st.token) for t in (query_token, cookie_token, header_token))


def _cookie_name(st) -> str:
    return f"apptok_{st.port}"


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
    cookies = "; ".join(c.strip() for c in request.headers.get("cookie", "").split(";") if c.strip() and not c.strip().startswith(_cookie_name(st) + "="))
    if cookies:
        h["cookie"] = cookies  # 접근 토큰 쿠키는 앱에 넘기지 않는다
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


def make_gateway(host, app_id: str) -> Starlette:
    def state():
        return host.states.get(app_id)

    async def ready_upstream(st, wait: bool) -> Optional[int]:
        """업스트림 포트. 꺼져 있으면 깨운다 (wait=True 면 APP_WAKE_WAIT_SECONDS 까지 기다림). 아직 준비 안 됐으면 None."""
        if st.status == "running" and st.upstream:
            return st.upstream
        task = host.wake(app_id)
        if wait:
            try:
                await asyncio.wait_for(asyncio.shield(task), settings.APP_WAKE_WAIT_SECONDS)
            except (asyncio.TimeoutError, Exception):  # noqa: BLE001
                pass
        return st.upstream if st.status == "running" else None

    async def authorize(request: Request, st) -> Optional[Response]:
        """인증 실패 응답을 돌려준다. 통과면 None. 쿼리로 토큰이 오면 쿠키를 심고 토큰이 없는 주소로 리다이렉트한다."""
        qt = request.query_params.get("t")
        if not token_ok(st, qt, request.cookies.get(_cookie_name(st)), request.headers.get("x-app-token")):
            return _error_page("접근 토큰이 필요합니다", "이 앱은 비공개입니다. 공유받은 링크(?t=...)로 접속하세요.", 401)
        if st.require_token and qt:
            params = [(k, v) for k, v in request.query_params.multi_items() if k != "t"]
            url = request.url.path + (("?" + urlencode(params)) if params else "")
            resp = RedirectResponse(url, status_code=303)
            resp.set_cookie(_cookie_name(st), st.token, httponly=True, samesite="lax", path="/")
            return resp
        return None

    async def status(request: Request):
        st = state()
        if not st:
            return JSONResponse({"status": "missing", "ready": False, "message": "앱을 찾을 수 없습니다"}, status_code=404)
        denied = await authorize(request, st)
        if denied is not None and denied.status_code == 401:
            return JSONResponse({"detail": "token required"}, status_code=401)
        if st.status == "stopped":
            host.wake(app_id)
        msg = host.cooldown_message(st) or {"starting": "앱을 시작하는 중...", "stopped": "앱을 깨우는 중...", "running": "준비되었습니다", "failed": st.error or "실패"}.get(st.status, "")
        return JSONResponse({"status": st.status, "ready": st.status == "running", "message": msg})

    async def proxy(request: Request):
        st = state()
        if not st:
            return _error_page("앱을 찾을 수 없습니다", "삭제된 앱입니다.", 404)
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
        url = f"http://127.0.0.1:{up}{request.url.path}" + (f"?{_strip_token(request)}" if request.url.query else "")
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
        return StreamingResponse(resp.aiter_raw(), status_code=resp.status_code, headers=headers, background=BackgroundTask(resp.aclose))

    async def _upstream_lost(st):
        """업스트림 연결이 끊겼다면 컨테이너가 아직 살아 있는지 확인하고, 아니면 stopped 로 돌려 다음 요청이 깨우게 한다."""
        if st.container_id and not await host._manager().is_running(st.container_id):
            st.status, st.upstream, st.container_id = "stopped", None, None
            await host._persist(st.id, status="stopped", container_id=None)

    async def ws_proxy(ws: WebSocket):
        st = state()
        if not st or not token_ok(st, ws.query_params.get("t"), ws.cookies.get(_cookie_name(st)), ws.headers.get("x-app-token")):
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
            if ws.client_state == WebSocketState.CONNECTING:
                await ws.close(code=1011)
            elif ws.client_state == WebSocketState.CONNECTED:
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


def _strip_token(request) -> str:
    """접근 토큰(t)은 앱에 넘기지 않는다."""
    items = [(k, v) for k, v in request.query_params.multi_items() if k != "t"]
    return urlencode(items)

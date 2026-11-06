"""내장 브라우저: 로그인 상태(프로필) 관리, 에이전트의 로그인 요청, 실시간 브라우저 화면(WebSocket).

실시간 화면은 sandbox 안의 브라우저 데몬에서 JPEG 프레임을 주기적으로 받아 화면(웹 UI)으로 전달하고,
사용자의 클릭·키 입력·주소 이동을 데몬으로 되돌려 보낸다. 입력은 브라우저로만 가며 LLM 에는 전달되지 않는다.
"""
import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.login_requests import PendingLogins
from app.db.session import AsyncSessionLocal, get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.services.browser_profile_service import BrowserProfileService
from app.services.sandbox_service import resolve_scope

logger = logging.getLogger(__name__)
router = APIRouter()
ws_router = APIRouter()

LIVE_MAX_SECONDS = 30 * 60
FRAME_INTERVAL = 0.7


class Domain(BaseModel):
    domain: str
    cookies: int


class ProfileInfo(BaseModel):
    has_profile: bool
    domains: list[Domain] = []
    size_bytes: int = 0
    updated_at: Optional[datetime] = None


class LoginRequestInfo(BaseModel):
    site: str
    url: str = ""
    reason: str = ""


class LoginDone(BaseModel):
    conversation_id: str
    cancelled: bool = False


@router.get("/profile", response_model=ProfileInfo)
async def get_profile(current_user: User = Depends(get_current_user)):
    return await BrowserProfileService.info(current_user.id)


@router.delete("/profile")
async def delete_profile(current_user: User = Depends(get_current_user)):
    await BrowserProfileService.delete(current_user.id)
    return {"status": "ok"}


@router.delete("/profile/domains/{domain}")
async def delete_profile_domain(domain: str, current_user: User = Depends(get_current_user)):
    if not await BrowserProfileService.delete(current_user.id, domain):
        raise HTTPException(status_code=404, detail="저장된 로그인 상태가 없습니다")
    return {"status": "ok"}


@router.get("/login-request", response_model=Optional[LoginRequestInfo])
async def get_login_request(conversation_id: str, current_user: User = Depends(get_current_user)):
    """이 대화에서 에이전트가 기다리는 로그인 요청 (없으면 null)."""
    return PendingLogins.get(conversation_id, current_user.id)


@router.post("/login-request/done")
async def finish_login_request(data: LoginDone, current_user: User = Depends(get_current_user)):
    if not PendingLogins.resolve(data.conversation_id, current_user.id, data.cancelled):
        raise HTTPException(status_code=404, detail="대기 중인 로그인 요청이 없습니다 (이미 처리했거나 시간이 초과되었습니다)")
    return {"status": "ok"}


# ── 실시간 브라우저 ───────────────────────────────────────────────────────────
def _normalize_url(raw: str) -> Optional[str]:
    raw = (raw or "").strip()
    if not raw or len(raw) > 2000:
        return None
    if "://" not in raw:
        raw = "https://" + raw
    u = urlparse(raw)
    return raw if u.scheme in ("http", "https") and u.hostname else None


@ws_router.websocket("/browser/live")
async def browser_live(websocket: WebSocket):
    from app.api.ws import _get_user_from_token
    from app.tools.browser_tools import DAEMON_VERSION, browser_call, daemon_post, persist_profile
    from app.tools.workspace_tools import _container

    user = await _get_user_from_token(websocket.query_params.get("token") or "")
    if not user:
        await websocket.close(code=4001)
        return
    conversation_id = websocket.query_params.get("conversation_id") or None
    try:
        async with AsyncSessionLocal() as db:
            scope = await resolve_scope(conversation_id, user.id, db) or ""
    except HTTPException:
        await websocket.close(code=4004)
        return
    await websocket.accept()

    async def send(obj: dict):
        await websocket.send_json(obj)

    try:
        res = await browser_call(user.id, {"cmd": "ping"}, timeout=60, sandbox_cid=scope)
        if res.get("ok") and res.get("v") != DAEMON_VERSION:  # 이전 버전 데몬은 다시 시작한다
            await browser_call(user.id, {"cmd": "close"}, timeout=10, sandbox_cid=scope)
            await asyncio.sleep(1)
            res = await browser_call(user.id, {"cmd": "ping"}, timeout=60, sandbox_cid=scope)
        if not res.get("ok"):
            await send({"t": "error", "message": str(res.get("error", "브라우저를 시작하지 못했습니다"))})
            await websocket.close()
            return
        cid = await _container(user.id, scope)
        await send({"t": "ready", "width": 1280, "height": 800})
    except Exception as e:
        logger.warning("[browser] live 시작 실패: %s", e)
        await send({"t": "error", "message": "브라우저를 시작하지 못했습니다"})
        await websocket.close()
        return

    lock = asyncio.Lock()
    wake = asyncio.Event()
    deadline = asyncio.get_running_loop().time() + LIVE_MAX_SECONDS

    async def frames():
        last = None
        while True:
            try:
                await asyncio.wait_for(wake.wait(), FRAME_INTERVAL)
            except asyncio.TimeoutError:
                pass
            wake.clear()
            if asyncio.get_running_loop().time() > deadline:
                await send({"t": "error", "message": "실시간 브라우저 사용 시간(30분)이 지났습니다. 다시 열어 주세요"})
                await websocket.close()
                return
            async with lock:
                f = await daemon_post(cid, {"cmd": "frame"}, timeout=20)
            if not f.get("ok"):
                continue
            digest = hashlib.md5(f["img"].encode()).hexdigest()
            if digest != last:
                last = digest
                await send({"t": "frame", "img": f["img"], "url": f.get("url", ""), "title": f.get("title", "")})

    async def do(msg: dict):
        t = msg.get("t")
        cmd: Optional[dict] = None
        if t == "click":
            cmd = {"cmd": "mouse", "x": float(msg["x"]), "y": float(msg["y"]), "button": msg.get("button") if msg.get("button") in ("left", "right") else "left", "count": min(int(msg.get("count") or 1), 2)}
        elif t == "wheel":
            cmd = {"cmd": "wheel", "x": float(msg.get("x") or 640), "y": float(msg.get("y") or 400), "dy": max(-2000.0, min(2000.0, float(msg.get("dy") or 0)))}
        elif t == "text":
            cmd = {"cmd": "insert", "text": str(msg.get("text") or "")[:2000]}
        elif t == "key":
            cmd = {"cmd": "keypress", "key": str(msg.get("key") or "")[:30]}
        elif t == "goto":
            url = _normalize_url(str(msg.get("url") or ""))
            if not url:
                await send({"t": "notice", "message": "http/https 주소만 열 수 있습니다"})
                return
            cmd = {"cmd": "goto", "url": url}
        elif t in ("reload", "back"):
            cmd = {"cmd": t}
        elif t == "save":
            async with lock:
                domains = await persist_profile(user.id, scope)
            await send({"t": "saved", "domains": domains or []})
            return
        if cmd is None:
            return
        async with lock:
            r = await daemon_post(cid, cmd, timeout=45)
        if not r.get("ok"):
            await send({"t": "notice", "message": str(r.get("error", "실패"))[:200]})
        wake.set()

    ftask = asyncio.create_task(frames())
    try:
        while True:
            msg = await websocket.receive_json()
            try:
                await do(msg)
            except (KeyError, ValueError, TypeError):
                continue
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        ftask.cancel()
        # 창을 닫을 때도 로그인 상태를 저장해 둔다 (사용자가 로그인을 마치고 그냥 닫은 경우)
        try:
            await persist_profile(user.id, scope)
        except Exception:
            pass

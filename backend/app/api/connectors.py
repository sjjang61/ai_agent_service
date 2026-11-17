import html
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.services import connector_service as cs
from app.services.connector_service import ConnectorError, ConnectorService

router = APIRouter()


class ConnectorInfo(BaseModel):
    id: str
    name: str
    description: str
    category: str
    connect_kind: str = "account"  # account: 계정 로그인(OAuth) — 지금은 이것 하나
    connected: bool = False
    account_email: Optional[str] = None


class ConnectorList(BaseModel):
    configured: bool  # 서버에 Google OAuth 클라이언트가 설정돼 있는가
    redirect_uri: str  # Google Cloud 콘솔에 등록해야 하는 리디렉션 URI (설정 안내용)
    connectors: list[ConnectorInfo]


class ConnectResponse(BaseModel):
    auth_url: str


@router.get("", response_model=ConnectorList)
async def list_connectors(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    acc = await ConnectorService.account(current_user.id, db)
    on = set(acc.connectors or []) if acc else set()
    return ConnectorList(
        configured=cs.configured(),
        redirect_uri=cs.redirect_uri(),
        connectors=[
            ConnectorInfo(id=cid, name=c["name"], description=c["description"], category=c["category"],
                          connected=cid in on, account_email=acc.email if (acc and cid in on) else None)
            for cid, c in cs.CONNECTORS.items()
        ],
    )


@router.post("/{connector_id}/connect", response_model=ConnectResponse)
async def connect(connector_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """Google 인증 화면 주소를 돌려준다. 화면이 새 창으로 열고, 인증이 끝나면 콜백이 연결을 저장한다."""
    if connector_id not in cs.CONNECTORS:
        raise HTTPException(status_code=404, detail="알 수 없는 커넥터입니다")
    acc = await ConnectorService.account(current_user.id, db)
    try:
        return ConnectResponse(auth_url=cs.build_auth_url(current_user.id, connector_id, acc.scopes if acc else ""))
    except ConnectorError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{connector_id}")
async def disconnect(connector_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    if connector_id not in cs.CONNECTORS:
        raise HTTPException(status_code=404, detail="알 수 없는 커넥터입니다")
    await ConnectorService.disconnect(current_user.id, connector_id, db)
    return {"status": "disconnected"}


_PAGE = """<!doctype html><meta charset="utf-8"><title>{title}</title><style>
body{{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8f9fa;color:#222}}
.box{{text-align:center;max-width:420px;padding:24px}}h1{{font-size:20px}}p{{color:#555;line-height:1.6}}</style>
<div class="box"><h1>{title}</h1><p>{msg}</p></div>
<script>try{{window.opener&&window.opener.postMessage({payload},'*')}}catch(e){{}}{close}</script>"""


@router.get("/google/callback", response_class=HTMLResponse, include_in_schema=False)
async def google_callback(
    code: Optional[str] = Query(None), state: Optional[str] = Query(None), error: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
):
    """Google 이 인증을 마치고 브라우저를 돌려보내는 주소 (로그인 헤더가 없으므로 state 서명으로 사용자를 확인한다)."""
    def page(title: str, msg: str, ok: bool, cid: str = "") -> HTMLResponse:
        payload = '{type:"connector-connected",id:"%s"}' % cid if ok else '{type:"connector-error"}'
        return HTMLResponse(_PAGE.format(title=html.escape(title), msg=html.escape(msg), payload=payload, close="setTimeout(function(){window.close()},1200)" if ok else ""))

    if error or not code or not state:
        return page("연결하지 못했습니다", "Google 인증이 취소됐거나 실패했습니다. 이 창을 닫고 다시 시도해 주세요." if error else "잘못된 요청입니다.", False)
    try:
        _, cid = await ConnectorService.complete_oauth(code, state, db)
    except ConnectorError as e:
        return page("연결하지 못했습니다", str(e), False)
    return page("연결되었습니다", f"{cs.CONNECTORS[cid]['name']} 연결을 마쳤습니다. 이 창은 자동으로 닫힙니다.", True, cid)

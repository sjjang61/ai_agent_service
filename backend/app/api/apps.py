"""웹앱 배포 API: 배포된 앱 목록·상태·시작·중지·삭제·로그."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.services.app_policy import CATEGORIES
from app.services.app_service import AppService, DeployError, PublishError, app_url, launch_url

router = APIRouter()


class AppResponse(BaseModel):
    id: str
    name: str
    kind: str
    url: Optional[str]
    port: Optional[int]
    status: str
    error: Optional[str] = None
    version: int
    visibility: str = "private"
    moderation_status: str = ""
    moderation_note: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = []
    launch_count: int = 0
    conversation_id: Optional[str] = None
    artifact_size: int = 0
    last_request_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DeployRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    path: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None
    kind: str = "auto"
    private: Optional[bool] = None  # 호환용(무시). 새 앱은 항상 비공개


class ListingRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    category: Optional[str] = None
    tags: List[str] = []
    accept_terms: bool = False


def _resp(rec) -> AppResponse:
    AppService.live(rec)
    return AppResponse(id=rec.id, name=rec.name, kind=rec.kind, url=app_url(rec), port=rec.proxy_port, status=rec.status, error=rec.error,
                       version=rec.version, visibility=rec.visibility or "private", moderation_status=rec.moderation_status or "", moderation_note=rec.moderation_note,
                       title=rec.title, description=rec.description, category=rec.category, tags=rec.tags or [], launch_count=rec.launch_count or 0, conversation_id=rec.conversation_id, artifact_size=rec.artifact_size or 0,
                       last_request_at=rec.last_request_at, created_at=rec.created_at, updated_at=rec.updated_at)


async def _own(app_id: str, user: User, db: AsyncSession):
    rec = await AppService.get(user.id, app_id, db)
    if not rec:
        raise HTTPException(status_code=404, detail="앱을 찾을 수 없습니다")
    return rec


@router.get("/info")
async def info():
    return {"enabled": settings.APP_HOST_ENABLED, "port_start": settings.APP_PORT_START, "port_end": settings.APP_PORT_END,
            "max_per_user": settings.APP_MAX_PER_USER, "idle_minutes": settings.APP_IDLE_MINUTES, "categories": CATEGORIES}


@router.get("", response_model=List[AppResponse])
async def list_apps(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return [_resp(r) for r in await AppService.list_for_user(current_user.id, db)]


@router.post("", response_model=AppResponse)
async def deploy_app(data: DeployRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    if not settings.APP_HOST_ENABLED:
        raise HTTPException(status_code=400, detail="웹앱 배포 기능이 꺼져 있습니다")
    try:
        return _resp(await AppService.deploy(current_user.id, db, data.conversation_id, data.name, data.path, data.kind, data.private))
    except DeployError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{app_id}", response_model=AppResponse)
async def get_app(app_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return _resp(await _own(app_id, current_user, db))


@router.post("/{app_id}/launch")
async def launch_app(app_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """앱을 여는 주소. 비공개 앱은 소유자에게 일회용 실행 티켓(60초)이 붙은 주소를, 공개 앱은 공개 주소를 준다."""
    rec = await _own(app_id, current_user, db)
    from app.services.app_host import host

    st = host.states.get(rec.id)
    if st and st.status == "stopped":
        host.wake(rec.id)  # 미리 깨워 둔다
    return {"url": launch_url(rec, current_user.id)}


@router.post("/{app_id}/publish", response_model=AppResponse)
async def publish_app(app_id: str, data: ListingRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """App Store 에 등록(공개). 등록 전 점검에 걸리면 거부된다. 정적 앱은 즉시 공개, 서버형 앱은 관리자 승인 후 공개."""
    if not data.accept_terms:
        raise HTTPException(status_code=400, detail="공개 약관에 동의해야 등록할 수 있습니다")
    rec = await _own(app_id, current_user, db)
    try:
        return _resp(await AppService.publish(rec, db, data.title, data.description, data.category, data.tags))
    except PublishError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{app_id}/listing", response_model=AppResponse)
async def update_listing(app_id: str, data: ListingRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    rec = await _own(app_id, current_user, db)
    try:
        return _resp(await AppService.update_listing(rec, db, data.title, data.description, data.category, data.tags))
    except PublishError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{app_id}/unpublish", response_model=AppResponse)
async def unpublish_app(app_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return _resp(await AppService.unpublish(await _own(app_id, current_user, db), db))


@router.post("/{app_id}/start", response_model=AppResponse)
async def start_app(app_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    rec = await _own(app_id, current_user, db)
    await AppService.start(rec)
    await db.refresh(rec)
    return _resp(rec)


@router.post("/{app_id}/stop", response_model=AppResponse)
async def stop_app(app_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    rec = await _own(app_id, current_user, db)
    await AppService.stop(rec)
    await db.refresh(rec)
    return _resp(rec)


@router.delete("/{app_id}")
async def delete_app(app_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    await AppService.delete(await _own(app_id, current_user, db), db)
    return {"status": "deleted"}


@router.get("/{app_id}/logs")
async def app_logs(app_id: str, lines: int = Query(100, ge=1, le=500), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return {"logs": await AppService.logs(await _own(app_id, current_user, db), lines)}

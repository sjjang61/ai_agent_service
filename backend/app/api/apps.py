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
from app.services.app_service import AppService, DeployError, app_url

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
    require_token: bool
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
    private: Optional[bool] = None


def _resp(rec) -> AppResponse:
    AppService.live(rec)
    return AppResponse(id=rec.id, name=rec.name, kind=rec.kind, url=app_url(rec), port=rec.proxy_port, status=rec.status, error=rec.error,
                       version=rec.version, require_token=bool(rec.require_token), conversation_id=rec.conversation_id, artifact_size=rec.artifact_size or 0,
                       last_request_at=rec.last_request_at, created_at=rec.created_at, updated_at=rec.updated_at)


async def _own(app_id: str, user: User, db: AsyncSession):
    rec = await AppService.get(user.id, app_id, db)
    if not rec:
        raise HTTPException(status_code=404, detail="앱을 찾을 수 없습니다")
    return rec


@router.get("/info")
async def info():
    return {"enabled": settings.APP_HOST_ENABLED, "port_start": settings.APP_PORT_START, "port_end": settings.APP_PORT_END,
            "max_per_user": settings.APP_MAX_PER_USER, "idle_minutes": settings.APP_IDLE_MINUTES}


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

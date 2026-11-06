"""App Store API: 공개된 웹앱 목록·상세·열기·신고, 관리자 검수."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.published_app import AppReport, PublishedApp
from app.models.user import User
from app.services.app_host import host
from app.services.app_policy import CATEGORIES, is_admin_email, public_url
from app.services.app_service import AppService, PublishError, is_public

router = APIRouter()


class StoreApp(BaseModel):
    id: str
    slug: str
    title: str
    description: str = ""
    category: str = "other"
    tags: List[str] = []
    owner_name: str = ""
    version: int
    kind: str
    launch_count: int = 0
    listed_at: Optional[datetime] = None
    url: str


def _item(rec: PublishedApp, owner: str) -> StoreApp:
    return StoreApp(id=rec.id, slug=rec.slug or "", title=rec.title or rec.name, description=rec.description or "", category=rec.category or "other",
                    tags=rec.tags or [], owner_name=owner or "", version=rec.version, kind=rec.kind, launch_count=rec.launch_count or 0,
                    listed_at=rec.listed_at, url=public_url(rec.slug or ""))


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not is_admin_email(user.email):
        raise HTTPException(status_code=403, detail="관리자만 사용할 수 있습니다")
    return user


@router.get("/info")
async def info(user: User = Depends(get_current_user)):
    return {"is_admin": is_admin_email(user.email), "categories": CATEGORIES}


@router.get("/apps", response_model=List[StoreApp])
async def list_store(q: Optional[str] = None, category: Optional[str] = None, sort: str = Query("popular", pattern="^(popular|new)$"),
                     limit: int = Query(60, ge=1, le=100), offset: int = Query(0, ge=0),
                     user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return [_item(r, o) for r, o in await AppService.store_list(db, q, category, sort, limit, offset)]


async def _public_app(app_id: str, db: AsyncSession) -> tuple:
    row = (await db.execute(select(PublishedApp, User.display_name).join(User, User.id == PublishedApp.user_id).where(PublishedApp.id == app_id))).first()
    if not row or not is_public(row[0]):
        raise HTTPException(status_code=404, detail="공개된 앱이 아닙니다")
    return row


@router.get("/apps/{app_id}", response_model=StoreApp)
async def get_store_app(app_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    rec, owner = await _public_app(app_id, db)
    return _item(rec, owner)


@router.post("/apps/{app_id}/launch")
async def launch_store_app(app_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """공개 앱의 접속 주소(호스트명 주소)를 주고 접속 수를 센다. 꺼져 있으면 미리 깨워 둔다."""
    rec, _ = await _public_app(app_id, db)
    st = host.states.get(rec.id)
    if st and st.status == "stopped":
        host.wake(rec.id)
    await AppService.count_launch(rec.id)
    return {"url": public_url(rec.slug or "")}


class ReportRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


@router.post("/apps/{app_id}/report")
async def report_store_app(app_id: str, data: ReportRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    rec, _ = await _public_app(app_id, db)
    if rec.user_id == user.id:
        raise HTTPException(status_code=400, detail="내 앱은 신고할 수 없습니다")
    try:
        count = await AppService.report(rec, user.id, data.reason, db)
    except PublishError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"reported": True, "count": count}


# ── 관리자 ─────────────────────────────────────────────────────────────────────
class QueueItem(StoreApp):
    moderation_status: str
    moderation_note: Optional[str] = None
    reports: int = 0
    reasons: List[str] = []


@router.get("/admin/queue", response_model=List[QueueItem])
async def admin_queue(status: str = Query("pending", pattern="^(pending|suspended|approved|rejected)$"),
                      admin: User = Depends(require_admin), db: AsyncSession = Depends(get_session)):
    """검수 큐. pending(승인 대기) | suspended(정지) | approved(공개 중, 신고 많은 순) | rejected."""
    rows = (await db.execute(select(PublishedApp, User.display_name).join(User, User.id == PublishedApp.user_id).where(
        PublishedApp.moderation_status == status))).all()
    ids = [r.id for r, _ in rows]
    counts, reasons = {}, {}
    if ids:
        counts = dict((await db.execute(select(AppReport.app_id, func.count()).where(AppReport.app_id.in_(ids)).group_by(AppReport.app_id))).all())
        for aid, reason in (await db.execute(select(AppReport.app_id, AppReport.reason).where(AppReport.app_id.in_(ids)).order_by(AppReport.created_at.desc()))).all():
            reasons.setdefault(aid, []).append(reason)
    out = []
    for r, owner in rows:
        base = _item(r, owner).model_dump()
        out.append(QueueItem(**base, moderation_status=r.moderation_status, moderation_note=r.moderation_note, reports=counts.get(r.id, 0), reasons=reasons.get(r.id, [])[:5]))
    return sorted(out, key=lambda i: -i.reports)


class ModerateRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject|suspend)$")
    note: Optional[str] = Field(default=None, max_length=1000)


@router.post("/admin/apps/{app_id}/moderate")
async def admin_moderate(app_id: str, data: ModerateRequest, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_session)):
    rec = await db.get(PublishedApp, app_id)
    if not rec:
        raise HTTPException(status_code=404, detail="앱을 찾을 수 없습니다")
    try:
        rec = await AppService.moderate(rec, db, data.action, data.note)
    except PublishError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": rec.id, "visibility": rec.visibility, "moderation_status": rec.moderation_status}

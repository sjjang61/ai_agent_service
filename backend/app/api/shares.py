"""대화 공유 API: 소유자용(공유·해제·상태)과 로그인 없이 읽는 공개 조회"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.services.app_policy import RateLimiter
from app.services.share_service import ShareService

router = APIRouter()  # /api/chat/conversations/{id}/share  (로그인 필요)
public_router = APIRouter()  # /api/shared/{token}          (로그인 없음)

_read_limiter = RateLimiter(settings.SHARE_RATE_PER_MIN)


def _status(rec) -> dict:
    if rec is None:
        return {"shared": False}
    return {
        "shared": True,
        "token": rec.token,
        "path": f"/share/{rec.token}",
        "message_count": rec.message_count,
        "view_count": rec.view_count,
        "shared_at": rec.updated_at.isoformat() if rec.updated_at else None,
        "expires_at": rec.expires_at.isoformat() if rec.expires_at else None,
    }


@router.get("/conversations/{conversation_id}/share")
async def share_status(conversation_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return _status(await ShareService.get(conversation_id, current_user.id, db))


@router.post("/conversations/{conversation_id}/share")
async def share_conversation(conversation_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """공유 링크를 만들거나(처음), 같은 주소의 내용을 지금 대화로 갱신한다(다시 호출)."""
    try:
        rec = await ShareService.share(conversation_id, current_user.id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if rec is None:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")
    return _status(rec)


@router.delete("/conversations/{conversation_id}/share")
async def unshare_conversation(conversation_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    await ShareService.unshare(conversation_id, current_user.id, db)
    return {"shared": False}


@public_router.get("/{token}")
async def read_shared(token: str, request: Request, db: AsyncSession = Depends(get_session)):
    ip = request.client.host if request.client else ""
    if not _read_limiter.allow(ip):
        return JSONResponse({"detail": "요청이 너무 많습니다. 잠시 후 다시 시도하세요"}, status_code=429, headers={"Retry-After": "30"})
    rec = await ShareService.public(token, db)
    if rec is None:
        raise HTTPException(status_code=404, detail="공유가 해제되었거나 존재하지 않는 링크입니다")
    return JSONResponse(
        {"title": rec.title, "messages": rec.snapshot or [], "shared_at": rec.updated_at.isoformat() if rec.updated_at else None},
        # 검색엔진 색인과 중간 캐시를 막는다 (해제 즉시 끊겨야 한다)
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
    )

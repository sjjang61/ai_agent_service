from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.channel_account import ChannelAccount
from app.models.user import User
from app.services.channel_service import ChannelService

router = APIRouter()


class ConnectRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class EnabledRequest(BaseModel):
    enabled: Optional[bool] = None
    notify_schedules: Optional[bool] = None


class ChannelStatus(BaseModel):
    configured: bool
    bot_username: Optional[str] = None
    enabled: bool = False
    notify_schedules: bool = True
    status: str = "none"  # none | pending | connected | error
    last_error: Optional[str] = None
    pair_code: Optional[str] = None  # 발급 직후 응답에만 포함된다 (저장은 해시)
    pair_expires_at: Optional[datetime] = None
    pair_url: Optional[str] = None


def _view(acc: Optional[ChannelAccount], code: Optional[str] = None) -> ChannelStatus:
    if acc is None:
        return ChannelStatus(configured=False)
    return ChannelStatus(
        configured=True, bot_username=acc.bot_username, enabled=bool(acc.enabled), notify_schedules=bool(acc.notify_schedules), status=acc.status, last_error=acc.last_error,
        pair_code=code, pair_expires_at=acc.pair_expires_at if code else None,
        pair_url=f"https://t.me/{acc.bot_username}?start={code}" if code and acc.bot_username else None,
    )


@router.get("/telegram", response_model=ChannelStatus)
async def get_telegram(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return _view(await ChannelService.get(user.id, db))


@router.put("/telegram", response_model=ChannelStatus)
async def connect_telegram(data: ConnectRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """봇 토큰 등록(또는 교체) + 연결 코드 발급."""
    acc, code = await ChannelService.connect(user.id, data.token, db)
    return _view(acc, code)


@router.post("/telegram/pair-code", response_model=ChannelStatus)
async def new_pair_code(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    acc, code = await ChannelService.reissue_code(user.id, db)
    return _view(acc, code)


@router.patch("/telegram", response_model=ChannelStatus)
async def set_enabled(data: EnabledRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return _view(await ChannelService.update(user.id, data.enabled, data.notify_schedules, db))


@router.delete("/telegram")
async def disconnect_telegram(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    await ChannelService.disconnect(user.id, db)
    return {"status": "deleted"}

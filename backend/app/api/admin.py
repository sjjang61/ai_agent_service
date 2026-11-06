from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.admin import (
    DailyUsageResponse,
    ModelUsageResponse,
    PricingRefreshResult,
    PricingState,
    PricingUrlRequest,
    SessionUsageResponse,
    UsageSummaryResponse,
    UserUsageResponse,
)
from app.services.token_usage_service import TokenUsageService

router = APIRouter()


@router.get("/usage/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    data = await TokenUsageService.get_summary(db, user_id)
    return UsageSummaryResponse(**data)


@router.get("/usage/daily", response_model=List[DailyUsageResponse])
async def get_daily_usage(
    days: int = Query(default=30, ge=1, le=365),
    user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    data = await TokenUsageService.get_daily_usage(db, days, user_id)
    return [DailyUsageResponse(**d) for d in data]


@router.get("/usage/weekly", response_model=List[DailyUsageResponse])
async def get_weekly_usage(
    weeks: int = Query(default=12, ge=1, le=52),
    user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    data = await TokenUsageService.get_weekly_usage(db, weeks, user_id)
    return [DailyUsageResponse(**d) for d in data]


@router.get("/usage/monthly", response_model=List[DailyUsageResponse])
async def get_monthly_usage(
    months: int = Query(default=12, ge=1, le=24),
    user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    data = await TokenUsageService.get_monthly_usage(db, months, user_id)
    return [DailyUsageResponse(**d) for d in data]


@router.get("/usage/users", response_model=List[UserUsageResponse])
async def get_user_breakdown(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    data = await TokenUsageService.get_user_breakdown(db, days)
    return [UserUsageResponse(**d) for d in data]


@router.get("/usage/models", response_model=List[ModelUsageResponse])
async def get_model_breakdown(
    days: int = Query(default=30, ge=1, le=365),
    user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    data = await TokenUsageService.get_model_breakdown(db, days, user_id)
    return [ModelUsageResponse(**d) for d in data]


@router.get("/usage/sessions/{conversation_id}", response_model=SessionUsageResponse)
async def get_session_usage(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    data = await TokenUsageService.get_session_usage(db, conversation_id)
    return SessionUsageResponse(**data)


# ── 가격 정책 (예상 비용 계산에 쓰는 모델 단가) ────────────────────────────────
async def _pricing_state(db: AsyncSession) -> PricingState:
    from app.services import pricing, pricing_update

    await pricing.refresh_if_stale(db)
    return PricingState(**await pricing_update.get_state(db), prices=pricing.effective_prices())


@router.get("/pricing", response_model=PricingState)
async def get_pricing(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """가격 정책 URL, 마지막 갱신 결과, 현재 적용 중인 모델 단가 (출처 포함)."""
    return await _pricing_state(db)


@router.put("/pricing/url", response_model=PricingState)
async def set_pricing_url(
    data: PricingUrlRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """가격 정책 URL 을 바꾼다 (https·공인 주소만)."""
    from app.services import pricing_update

    try:
        await pricing_update.set_url(db, data.url)
    except pricing_update.PricingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await _pricing_state(db)


@router.post("/pricing/refresh", response_model=PricingRefreshResult)
async def refresh_pricing(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """저장된 URL 의 가격 페이지를 읽어 모델 단가를 갱신한다."""
    from app.services import pricing_update

    try:
        return PricingRefreshResult(**await pricing_update.refresh(db))
    except pricing_update.PricingError as e:
        raise HTTPException(status_code=400, detail=str(e))

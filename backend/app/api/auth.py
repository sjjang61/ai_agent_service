from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse, SimpleLoginRequest
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", response_model=UserResponse)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_session)):
    user = await AuthService.register(data, db)
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_session)):
    return await AuthService.login(data, db)


class SimpleLoginResponse(TokenResponse):
    user: UserResponse


@router.post("/simple-login", response_model=SimpleLoginResponse)
async def simple_login(data: SimpleLoginRequest, db: AsyncSession = Depends(get_session)):
    """비밀번호 없이 login_id 만으로 로그인. 사용자가 없으면 자동 생성."""
    token, user = await AuthService.simple_login(data, db)
    return SimpleLoginResponse(
        access_token=token.access_token,
        refresh_token=token.refresh_token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )

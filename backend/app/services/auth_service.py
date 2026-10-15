from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, SimpleLoginRequest


class AuthService:
    @staticmethod
    async def register(data: RegisterRequest, db: AsyncSession) -> User:
        result = await db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")
        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            display_name=data.display_name,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def login(data: LoginRequest, db: AsyncSession) -> TokenResponse:
        result = await db.execute(select(User).where(User.email == data.email))
        user = result.scalar_one_or_none()
        if not user or not verify_password(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    @staticmethod
    async def simple_login(data: SimpleLoginRequest, db: AsyncSession) -> tuple[TokenResponse, User]:
        """비밀번호 없이 login_id 만으로 로그인. 사용자가 없으면 자동 생성."""
        login_id = data.login_id.strip()
        if not login_id:
            raise HTTPException(status_code=400, detail="Login ID is required")

        # login_id를 email 형태로 변환 (@ 없으면 추가)
        email = login_id if "@" in login_id else f"{login_id}@local"

        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            # 사용자 자동 생성
            user = User(
                email=email,
                hashed_password=hash_password("no-password"),  # 더미 비밀번호
                display_name=login_id,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        token = TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )
        return token, user

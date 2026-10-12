from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse


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

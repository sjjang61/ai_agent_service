from fastapi import Depends, HTTPException, status, WebSocket
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.core.security import decode_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == payload.get("sub")))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_ws_user(websocket: WebSocket, db: AsyncSession = Depends(get_db)) -> User:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=4001)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    result = await db.execute(select(User).where(User.id == payload.get("sub")))
    user = result.scalar_one_or_none()
    if not user:
        await websocket.close(code=4001)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user

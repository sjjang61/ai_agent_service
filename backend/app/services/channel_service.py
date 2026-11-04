"""메신저 채널 연동 관리: 봇 등록, 연결(pairing) 코드, 해제."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.telegram_api import TelegramClient, TelegramError
from app.config import settings
from app.core.crypto import decrypt, encrypt
from app.models.channel_account import ChannelAccount

CHANNEL = "telegram"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # DB 는 UTC naive


def hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode()).hexdigest()


def new_code() -> str:
    return secrets.token_hex(4).upper()  # 8자리 16진수


class ChannelService:
    @staticmethod
    async def get(user_id: str, db: AsyncSession) -> Optional[ChannelAccount]:
        r = await db.execute(select(ChannelAccount).where(ChannelAccount.user_id == user_id, ChannelAccount.channel == CHANNEL))
        return r.scalar_one_or_none()

    @staticmethod
    def _issue_code(acc: ChannelAccount) -> str:
        code = new_code()
        acc.pair_code_hash = hash_code(code)
        acc.pair_expires_at = _now() + timedelta(seconds=settings.CHANNEL_PAIR_TTL_SECONDS)
        return code

    @staticmethod
    async def connect(user_id: str, token: str, db: AsyncSession) -> tuple[ChannelAccount, str]:
        """봇 토큰을 검증해 저장하고 연결 코드를 발급한다. 같은 사용자가 다시 등록하면 교체(연결은 해제)한다."""
        token = token.strip()
        client = TelegramClient(token)
        try:
            me = await client.get_me()
            await client.delete_webhook()  # long polling 은 webhook 이 걸려 있으면 동작하지 않는다
        except TelegramError as e:
            raise HTTPException(status_code=422, detail=f"봇 토큰을 확인할 수 없습니다: {e.description or '네트워크 오류'}")
        finally:
            await client.aclose()
        # 같은 봇을 다른 사용자가 이미 쓰고 있으면 거절한다 (한 봇의 getUpdates 는 한 곳에서만 가능)
        for other in (await db.execute(select(ChannelAccount).where(ChannelAccount.channel == CHANNEL, ChannelAccount.user_id != user_id))).scalars():
            try:
                if decrypt(other.token_enc) == token:
                    raise HTTPException(status_code=409, detail="이미 다른 계정에 연결된 봇입니다")
            except ValueError:
                continue
        acc = await ChannelService.get(user_id, db)
        if acc is None:
            acc = ChannelAccount(user_id=user_id, channel=CHANNEL, token_enc="")
            db.add(acc)
        acc.token_enc = encrypt(token)
        acc.bot_username = me.get("username")
        acc.enabled = True
        acc.status, acc.last_error = "pending", None
        acc.external_user_id = acc.chat_id = acc.conversation_id = None
        acc.last_update_id = 0
        code = ChannelService._issue_code(acc)
        await db.commit()
        await db.refresh(acc)
        return acc, code

    @staticmethod
    async def reissue_code(user_id: str, db: AsyncSession) -> tuple[ChannelAccount, str]:
        acc = await ChannelService.get(user_id, db)
        if acc is None:
            raise HTTPException(status_code=404, detail="등록된 봇이 없습니다")
        acc.external_user_id = acc.chat_id = None  # 다시 연결하는 것이므로 기존 연결은 끊는다
        acc.status = "pending"
        code = ChannelService._issue_code(acc)
        await db.commit()
        return acc, code

    @staticmethod
    async def update(user_id: str, enabled: Optional[bool], notify_schedules: Optional[bool], db: AsyncSession) -> ChannelAccount:
        acc = await ChannelService.get(user_id, db)
        if acc is None:
            raise HTTPException(status_code=404, detail="등록된 봇이 없습니다")
        if enabled is not None:
            acc.enabled = enabled
            if enabled and acc.status == "error":
                acc.status = "connected" if acc.external_user_id else "pending"
                acc.last_error = None
        if notify_schedules is not None:
            acc.notify_schedules = notify_schedules
        await db.commit()
        return acc

    @staticmethod
    async def disconnect(user_id: str, db: AsyncSession) -> None:
        acc = await ChannelService.get(user_id, db)
        if acc is not None:
            await db.delete(acc)
            await db.commit()

    @staticmethod
    def try_pair(acc: ChannelAccount, code: str, external_user_id: int, chat_id: int) -> bool:
        """코드가 맞고 만료 전이면 이 Telegram 계정을 소유자로 연결한다 (코드는 1회용)."""
        if not acc.pair_code_hash or not acc.pair_expires_at or acc.pair_expires_at < _now():
            return False
        if not secrets.compare_digest(acc.pair_code_hash, hash_code(code)):
            return False
        acc.external_user_id, acc.chat_id = external_user_id, chat_id
        acc.pair_code_hash = acc.pair_expires_at = None
        acc.status, acc.last_error = "connected", None
        return True

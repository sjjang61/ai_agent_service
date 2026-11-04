"""에이전트 쪽에서 먼저 보내는 메시지 (예약 작업 결과 등)."""
import logging

from sqlalchemy import select

from app.channels.gateway import send_markdown
from app.channels.telegram_api import TelegramClient
from app.core.crypto import decrypt
from app.db.session import AsyncSessionLocal
from app.models.channel_account import ChannelAccount

logger = logging.getLogger(__name__)


async def notify_schedule_result(user_id: str, task_name: str, status: str, body: str, error: str | None = None) -> bool:
    """연결된 Telegram 채팅으로 예약 작업 결과를 보낸다. 연결·알림 설정이 없으면 아무것도 하지 않는다. 실패는 삼킨다."""
    try:
        async with AsyncSessionLocal() as db:
            acc = (
                await db.execute(
                    select(ChannelAccount).where(
                        ChannelAccount.user_id == user_id, ChannelAccount.channel == "telegram", ChannelAccount.enabled.is_(True),
                        ChannelAccount.notify_schedules.is_(True), ChannelAccount.chat_id.is_not(None),
                    )
                )
            ).scalar_one_or_none()
            if acc is None:
                return False
            token, chat_id = decrypt(acc.token_enc), acc.chat_id
        if status == "succeeded":
            text = f"⏰ {task_name}\n\n{body}"
        elif status == "cancelled":
            return False
        else:
            text = f"⚠️ 예약 작업 실패 · {task_name}\n{error or ''}"
        client = TelegramClient(token)
        try:
            await send_markdown(client, chat_id, text)
        finally:
            await client.aclose()
        return True
    except Exception:  # noqa: BLE001
        logger.exception("[channels] 예약 결과 전송 실패 user=%s", user_id)
        return False

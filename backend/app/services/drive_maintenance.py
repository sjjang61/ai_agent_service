"""Drive 주기 작업: 보관 기간이 지난 휴지통 묶음을 영구 삭제한다 (한 시간마다)."""
import asyncio
import logging

from app.db.session import AsyncSessionLocal
from app.services import drive_service

logger = logging.getLogger(__name__)
INTERVAL_SECONDS = 3600


async def run_drive_maintenance() -> None:
    while True:
        try:
            async with AsyncSessionLocal() as db:
                n = await drive_service.purge_expired(db)
                if n:
                    logger.info("[drive] 보관 기간이 지난 휴지통 %d건을 영구 삭제했습니다", n)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("[drive] 주기 작업 실패")
        await asyncio.sleep(INTERVAL_SECONDS)

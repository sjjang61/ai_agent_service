import asyncio
import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def run_idle_reaper():
    """미사용 sandbox 를 주기적으로 백업·종료하는 백그라운드 루프."""
    from app.services.sandbox_service import SandboxService, sandbox_backup

    if not sandbox_backup.enabled:
        logger.warning("[sandbox] MINIO_* 미설정 — idle sandbox 자동 백업/종료 비활성화")
    while True:
        try:
            await asyncio.sleep(settings.SANDBOX_REAPER_INTERVAL_SECONDS)
            await SandboxService.reap_idle()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("[sandbox] reaper 오류")

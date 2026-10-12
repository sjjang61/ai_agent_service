import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.sandbox import Sandbox
from app.sandbox.backup import SandboxBackup
from app.sandbox.manager import SandboxManager

logger = logging.getLogger(__name__)

sandbox_manager = SandboxManager()
sandbox_backup = SandboxBackup(sandbox_manager)

# 사용자별 생성/복구/종료 직렬화 (reaper 와 도구 호출의 경합 방지, 단일 프로세스 기준)
_locks: dict[str, asyncio.Lock] = {}


def _lock(user_id: str) -> asyncio.Lock:
    return _locks.setdefault(user_id, asyncio.Lock())


def _utcnow() -> datetime:
    # DB(MySQL DATETIME)에는 UTC naive 로 저장되므로 같은 형태로 비교한다
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SandboxService:
    """사용자당 sandbox 1개. Sandbox.id 가 곧 세션 id 이며 컨테이너가 바뀌어도 유지된다."""

    @staticmethod
    async def _latest(user_id: str, db: AsyncSession) -> Optional[Sandbox]:
        result = await db.execute(
            select(Sandbox)
            .where(Sandbox.user_id == user_id)
            .order_by(Sandbox.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    @staticmethod
    async def get_or_create_sandbox(user_id: str, db: AsyncSession) -> Sandbox:
        async with _lock(user_id):
            sb = await SandboxService._latest(user_id, db)
            if sb and sb.status == "running" and sb.container_id:
                if await sandbox_manager.is_running(sb.container_id):
                    sb.last_used_at = _utcnow()
                    await db.commit()
                    sb.restored = False
                    return sb
                logger.warning("[sandbox] session=%s 컨테이너가 없음 → 재생성", sb.id)

            # 같은 세션(행)을 재사용해서 세션 id 를 유지한다
            if sb is None:
                sb = Sandbox(user_id=user_id, status="stopped")
                db.add(sb)
                await db.flush()

            container_id = await sandbox_manager.create_sandbox(user_id)
            restored = False
            try:
                restored = await sandbox_backup.restore(sb.id, container_id)
            except Exception:
                logger.exception("[sandbox] session=%s 복구 실패 — 빈 workspace 로 시작", sb.id)

            sb.container_id = container_id
            sb.status = "running"
            sb.last_used_at = _utcnow()
            await db.commit()
            await db.refresh(sb)
            sb.restored = restored
            return sb

    @staticmethod
    async def get_sandbox(user_id: str, db: AsyncSession) -> Optional[Sandbox]:
        return await SandboxService._latest(user_id, db)

    @staticmethod
    async def touch(sb: Sandbox, db: AsyncSession):
        sb.last_used_at = _utcnow()
        await db.commit()

    @staticmethod
    async def suspend(
        sandbox_id: str, db: AsyncSession, idle_cutoff: Optional[datetime] = None
    ) -> str:
        """백업 후 컨테이너를 종료한다. idle_cutoff 가 있으면 그 이후 사용된 sandbox 는 건너뛴다.

        백업이 활성화되어 있는데 실패하면 예외를 던지고 컨테이너는 그대로 둔다 (데이터 보호).
        """
        sb = await db.get(Sandbox, sandbox_id)
        if not sb:
            return "missing"
        async with _lock(sb.user_id):
            await db.refresh(sb)
            if sb.status != "running" or not sb.container_id:
                return "skipped"
            if idle_cutoff and sb.last_used_at and sb.last_used_at > idle_cutoff:
                return "active"

            if await sandbox_manager.is_running(sb.container_id):
                if sandbox_backup.enabled:
                    await sandbox_backup.backup(sb.id, sb.container_id)
                await sandbox_manager.destroy_sandbox(sb.container_id)
            sb.status = "stopped"
            await db.commit()
            return "suspended"

    @staticmethod
    async def reap_idle() -> int:
        """last_used_at 이 SANDBOX_IDLE_MINUTES 이상 지난 sandbox 를 백업 후 종료."""
        if not sandbox_backup.enabled:
            return 0  # 백업 불가 시 자동 종료하지 않음 (데이터 유실 방지)
        from app.db.session import AsyncSessionLocal

        cutoff = _utcnow() - timedelta(minutes=settings.SANDBOX_IDLE_MINUTES)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Sandbox.id).where(Sandbox.status == "running", Sandbox.last_used_at < cutoff)
            )
            ids = list(result.scalars().all())

        count = 0
        for sid in ids:
            async with AsyncSessionLocal() as db:
                try:
                    if await SandboxService.suspend(sid, db, idle_cutoff=cutoff) == "suspended":
                        count += 1
                        logger.info("[sandbox] idle 종료 session=%s", sid)
                except Exception:
                    logger.exception("[sandbox] session=%s 백업/종료 실패 — 다음 주기에 재시도", sid)
        return count

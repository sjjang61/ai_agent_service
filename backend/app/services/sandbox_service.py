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

# sandbox 별 생성/복구/종료 직렬화 (reaper 와 도구 호출의 경합 방지, 단일 프로세스 기준)
_locks: dict[str, asyncio.Lock] = {}


def _lock(user_id: str, conversation_id: Optional[str] = None) -> asyncio.Lock:
    return _locks.setdefault(f"{user_id}:{conversation_id or 'shared'}", asyncio.Lock())


def _utcnow() -> datetime:
    # DB(MySQL DATETIME)에는 UTC naive 로 저장되므로 같은 형태로 비교한다
    return datetime.now(timezone.utc).replace(tzinfo=None)


def backup_key(sb: Sandbox) -> str:
    """MinIO 백업 폴더 이름: 대화방 sandbox 는 대화방 id, 사용자 공용 sandbox 는 Sandbox.id."""
    return sb.conversation_id or sb.id


async def resolve_scope(conversation_id: Optional[str], user_id: str, db: AsyncSession) -> Optional[str]:
    """어떤 sandbox 를 쓸지 정한다. None = 사용자 단위 공용 sandbox, 값 = 그 대화방 전용 sandbox.
    대화방 id 가 없거나 스페이스에서 시작한 대화(space_id)면 공용을 쓴다. 남의 대화방 id 는 404."""
    if not conversation_id:
        return None
    from fastapi import HTTPException

    from app.models.conversation import Conversation

    row = (
        await db.execute(
            select(Conversation.space_id).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")
    return None if row[0] else conversation_id


class SandboxService:
    """sandbox 는 두 종류다. (1) 대화방 전용: 대화방마다 독립된 컨테이너·workspace·백업 (2) 사용자 공용(conversation_id=NULL):
    스페이스에서 시작한 대화와 대화방 도입 전의 기존 sandbox. 사용자당 공용 1개, 컨테이너가 바뀌어도 행(id)은 유지된다."""

    @staticmethod
    async def _find(user_id: str, db: AsyncSession, conversation_id: Optional[str] = None) -> Optional[Sandbox]:
        cond = Sandbox.conversation_id == conversation_id if conversation_id else Sandbox.conversation_id.is_(None)
        result = await db.execute(
            select(Sandbox).where(Sandbox.user_id == user_id, cond).order_by(Sandbox.created_at.desc()).limit(1)
        )
        return result.scalars().first()

    @staticmethod
    async def _enforce_running_cap(user_id: str, keep_conversation_id: Optional[str], db: AsyncSession) -> None:
        """사용자의 실행 중 sandbox 가 상한이면 가장 오래 쓰지 않은 것을 백업 후 종료해 자리를 만든다."""
        cap = settings.SANDBOX_MAX_RUNNING_PER_USER
        if cap <= 0:
            return
        r = await db.execute(
            select(Sandbox).where(Sandbox.user_id == user_id, Sandbox.status == "running").order_by(Sandbox.last_used_at.asc())
        )
        running = [x for x in r.scalars().all() if x.conversation_id != keep_conversation_id]
        for victim in running[: max(0, len(running) - cap + 1)]:
            try:
                await SandboxService.suspend(victim.id, db)
                logger.info("[sandbox] 동시 실행 상한(%d) — %s 를 백업 후 종료", cap, victim.conversation_id or "공용")
            except Exception:
                logger.exception("[sandbox] 상한 초과 sandbox 종료 실패 (계속 진행)")

    @staticmethod
    async def get_or_create_sandbox(user_id: str, db: AsyncSession, conversation_id: Optional[str] = None) -> Sandbox:
        async with _lock(user_id, conversation_id):
            sb = await SandboxService._find(user_id, db, conversation_id)
            if sb and sb.status == "running" and sb.container_id:
                if await sandbox_manager.is_running(sb.container_id):
                    sb.last_used_at = _utcnow()
                    await db.commit()
                    sb.restored = False
                    return sb
                logger.warning("[sandbox] session=%s 컨테이너가 없음 → 재생성", sb.id)

            await SandboxService._enforce_running_cap(user_id, conversation_id, db)

            # 같은 sandbox(행)를 재사용해서 id 를 유지한다
            if sb is None:
                sb = Sandbox(user_id=user_id, conversation_id=conversation_id, status="stopped")
                db.add(sb)
                await db.flush()

            container_id = await sandbox_manager.create_sandbox(user_id, conversation_id)
            restored = False
            try:
                restored = await sandbox_backup.restore(backup_key(sb), container_id)
            except Exception:
                logger.exception("[sandbox] session=%s 복구 실패 — 빈 workspace 로 시작", backup_key(sb))

            # 새 컨테이너의 /workspace 는 비어 있으므로(복구된 백업에 없는 경우 포함) 등록된 활성 skill 을 채운다
            try:
                from app.services.skill_service import SkillService

                active = [s for s in await SkillService.list_skills(user_id, db) if s.is_active]
                copied = await SkillService.ensure_in_sandbox(container_id, active)
                if copied:
                    logger.info("[sandbox] session=%s skill %d개를 새 sandbox 로 복사: %s", backup_key(sb), len(copied), ", ".join(copied))
            except Exception:
                logger.exception("[sandbox] session=%s skill 자동 복사 실패 (sandbox 는 계속 사용 가능)", backup_key(sb))

            sb.container_id = container_id
            sb.status = "running"
            sb.last_used_at = _utcnow()
            await db.commit()
            await db.refresh(sb)
            sb.restored = restored
            return sb

    @staticmethod
    async def restore_if_backed_up(user_id: str, conversation_id: Optional[str] = None) -> bool:
        """요청이 시작될 때 호출한다. 이 sandbox 가 꺼져 있고 MinIO 에 백업이 있으면 컨테이너를 만들어 복구한다
        (등록된 skill 도 함께 채워진다). 복구했으면 True.

        백업이 없으면 아무것도 하지 않는다 (sandbox 를 쓰지 않는 대화에서 컨테이너를 불필요하게 만들지 않는다).
        """
        if not sandbox_backup.enabled:
            return False
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            sb = await SandboxService._find(user_id, db, conversation_id)
            if sb is None:
                return False
            if sb.status == "running" and sb.container_id and await sandbox_manager.is_running(sb.container_id):
                return False
            if not await sandbox_backup.exists(backup_key(sb)):
                return False
            restored = await SandboxService.get_or_create_sandbox(user_id, db, conversation_id)
            logger.info("[sandbox] 요청 시작 시 복구 session=%s restored=%s", backup_key(restored), getattr(restored, "restored", None))
            return True

    @staticmethod
    async def get_sandbox(user_id: str, db: AsyncSession, conversation_id: Optional[str] = None) -> Optional[Sandbox]:
        return await SandboxService._find(user_id, db, conversation_id)

    @staticmethod
    async def list_for_user(user_id: str, db: AsyncSession) -> list:
        """내 sandbox 전체 (공용 + 대화방별) 와 대화방 제목."""
        from app.models.conversation import Conversation

        rows = (await db.execute(select(Sandbox).where(Sandbox.user_id == user_id).order_by(Sandbox.last_used_at.desc()))).scalars().all()
        ids = [r.conversation_id for r in rows if r.conversation_id]
        titles = {}
        if ids:
            titles = {i: t for i, t in (await db.execute(select(Conversation.id, Conversation.title).where(Conversation.id.in_(ids)))).all()}
        return [(r, titles.get(r.conversation_id)) for r in rows]

    @staticmethod
    async def delete_sandbox(sandbox_id: str, user_id: str, db: AsyncSession) -> bool:
        """sandbox 를 컨테이너·백업·행까지 모두 지운다 (백업은 하지 않는다)."""
        sb = await db.get(Sandbox, sandbox_id)
        if not sb or sb.user_id != user_id:
            return False
        async with _lock(sb.user_id, sb.conversation_id):
            if sb.container_id:
                await sandbox_manager.destroy_sandbox(sb.container_id)
            await sandbox_backup.delete(backup_key(sb))
            await db.delete(sb)
            await db.commit()
        return True

    @staticmethod
    async def delete_for_conversation(conversation_id: str, user_id: str, db: AsyncSession) -> None:
        """대화방을 삭제할 때 그 대화방의 sandbox(컨테이너·백업·행)를 함께 지운다. 실패해도 대화 삭제는 막지 않는다."""
        try:
            r = await db.execute(select(Sandbox.id).where(Sandbox.user_id == user_id, Sandbox.conversation_id == conversation_id))
            for sid in r.scalars().all():
                await SandboxService.delete_sandbox(sid, user_id, db)
            await sandbox_backup.delete(conversation_id)  # 행이 없어도 남은 백업이 있으면 정리
        except Exception:
            logger.exception("[sandbox] 대화방 %s 의 sandbox 정리 실패", conversation_id)

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
        async with _lock(sb.user_id, sb.conversation_id):
            await db.refresh(sb)
            if sb.status != "running" or not sb.container_id:
                return "skipped"
            if idle_cutoff and sb.last_used_at and sb.last_used_at > idle_cutoff:
                return "active"

            if await sandbox_manager.is_running(sb.container_id):
                if sandbox_backup.enabled:
                    await sandbox_backup.backup(backup_key(sb), sb.container_id)
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

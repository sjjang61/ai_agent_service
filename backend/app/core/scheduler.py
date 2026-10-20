"""예약 작업 스케줄러: 실행 시각이 된 작업을 주기적으로 찾아 한 회차씩 실행한다.

여러 서버 프로세스가 같은 DB 를 봐도 한 작업이 한 번만 실행되도록, next_run_at 을 읽은 값과 같을 때만 갱신하는
조건부 UPDATE 로 먼저 선점한 쪽만 실행한다. 놓친 실행은 유예 시간(SCHEDULER_MISFIRE_GRACE_SECONDS) 안이면 한 번만 실행한다.
"""
import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select, update

from app.config import settings
from app.models.scheduled_task import ScheduledTask, TaskRun
from app.services import schedule_calc as calc
from app.services.schedule_service import now_utc

logger = logging.getLogger(__name__)


def _next_after(task: ScheduledTask, after):
    return calc.compute_next_run(
        task.schedule_type, after, schedule_time=task.schedule_time, weekdays=task.weekdays,
        day_of_month=task.day_of_month, interval_hours=task.interval_hours, run_at=task.run_at, timezone_name=task.timezone,
    )


async def claim_due_tasks(db, now=None, limit: int = 20) -> list[tuple[str, str]]:
    """실행할 (task_id, run_id) 목록을 선점해서 돌려준다. 건너뛴 회차는 이력(skipped)만 남긴다."""
    from app.services.task_runner import create_run

    now = now or now_utc()
    rows = (await db.execute(
        select(ScheduledTask).where(ScheduledTask.enabled.is_(True), ScheduledTask.next_run_at.is_not(None), ScheduledTask.next_run_at <= now)
        .order_by(ScheduledTask.next_run_at).limit(limit)
    )).scalars().all()

    claimed = []
    grace = timedelta(seconds=settings.SCHEDULER_MISFIRE_GRACE_SECONDS)
    for t in rows:
        due = t.next_run_at
        new_next = _next_after(t, now)  # 놓친 회차를 몰아서 실행하지 않고 '지금 이후'의 다음 회차로 넘어간다
        res = await db.execute(
            update(ScheduledTask)
            .where(ScheduledTask.id == t.id, ScheduledTask.next_run_at == due, ScheduledTask.enabled.is_(True))
            .values(next_run_at=new_next)
        )
        await db.commit()
        if res.rowcount != 1:
            continue  # 다른 프로세스가 먼저 선점했다
        await db.refresh(t)
        if now - due > grace:
            await create_run(t, "schedule", due, db, status="skipped", error="서버 중단 등으로 실행 시각을 놓쳐 건너뛰었습니다")
            t.last_status = "skipped"
            await db.commit()
            continue
        run = await create_run(t, "schedule", due, db)
        claimed.append((t.id, run.id))
    return claimed


async def recover_stale_runs(db, now=None) -> int:
    """실행 시간 제한을 넘겨도 'running' 으로 남은 회차(서버 재시작 등)를 실패로 정리한다."""
    now = now or now_utc()
    limit = now - timedelta(seconds=settings.SCHEDULER_RUN_TIMEOUT_SECONDS + 120)
    res = await db.execute(
        update(TaskRun)
        .where(TaskRun.status.in_(("queued", "running")), TaskRun.created_at < limit)
        .values(status="failed", error="서버 재시작 등으로 실행이 중단되었습니다", finished_at=now)
    )
    await db.commit()
    return res.rowcount or 0


async def run_scheduler() -> None:
    from app.db.session import AsyncSessionLocal
    from app.services.task_runner import execute_run, spawn

    if not settings.SCHEDULER_ENABLED:
        logger.warning("[scheduler] SCHEDULER_ENABLED=false — 예약 작업 자동 실행이 꺼져 있습니다")
        return
    sem = asyncio.Semaphore(settings.SCHEDULER_MAX_CONCURRENT)

    async def guarded(run_id: str):
        async with sem:
            await execute_run(run_id)

    logger.info("[scheduler] 시작 (주기 %ss, 동시 %s개)", settings.SCHEDULER_POLL_SECONDS, settings.SCHEDULER_MAX_CONCURRENT)
    ticks = 0
    while True:
        try:
            async with AsyncSessionLocal() as db:
                if ticks % 10 == 0:
                    n = await recover_stale_runs(db)
                    if n:
                        logger.warning("[scheduler] 중단된 실행 %d건을 실패로 정리", n)
                for _task_id, run_id in await claim_due_tasks(db):
                    spawn(guarded(run_id))
            ticks += 1
            await asyncio.sleep(settings.SCHEDULER_POLL_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("[scheduler] 루프 오류")
            await asyncio.sleep(settings.SCHEDULER_POLL_SECONDS)

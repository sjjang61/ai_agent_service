"""예약 작업 CRUD · 상태 계산 · 읽지 않음 처리."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.scheduled_task import ScheduledTask, TaskRun
from app.schemas.schedule import RunResponse, TaskInput, TaskResponse, TaskUpdate
from app.services import schedule_calc as calc

SCHEDULE_FIELDS = (
    "schedule_type", "schedule_time", "weekdays", "day_of_month", "interval_hours", "run_at", "timezone",
)
# 결과를 확인해야 하는(알림 대상) 실행 상태
NOTIFY_STATUSES = ("succeeded", "failed")


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def aware(dt: Optional[datetime]) -> Optional[datetime]:
    """DB 의 UTC naive 시각을 UTC-aware 로 바꿔 JSON 에 '+00:00' 이 붙게 한다 (브라우저가 올바르게 해석)."""
    return dt.replace(tzinfo=timezone.utc) if dt is not None else None


def _spec(t: ScheduledTask) -> dict:
    return dict(
        schedule_time=t.schedule_time, weekdays=t.weekdays, day_of_month=t.day_of_month,
        interval_hours=t.interval_hours, run_at=t.run_at, timezone_name=t.timezone,
    )


def status_of(t: ScheduledTask) -> str:
    if not t.enabled:
        return "auto_paused" if t.last_status == "auto_paused" else "paused"
    if t.schedule_type == "once" and t.next_run_at is None and t.last_run_at is not None:
        return "completed"
    return "active"


def _validate(t_like: dict, now: Optional[datetime] = None) -> None:
    try:
        calc.validate_spec(
            t_like["schedule_type"],
            schedule_time=t_like.get("schedule_time"), weekdays=t_like.get("weekdays"),
            day_of_month=t_like.get("day_of_month"), interval_hours=t_like.get("interval_hours"),
            run_at=t_like.get("run_at"), timezone_name=t_like.get("timezone") or settings.SCHEDULER_DEFAULT_TIMEZONE,
            min_interval_hours=settings.SCHEDULER_MIN_INTERVAL_HOURS, now=now,
        )
    except calc.ScheduleError as e:
        raise HTTPException(status_code=422, detail=str(e))


def _next_run(t_like: dict, after: datetime) -> Optional[datetime]:
    return calc.compute_next_run(
        t_like["schedule_type"], after,
        schedule_time=t_like.get("schedule_time"), weekdays=t_like.get("weekdays"),
        day_of_month=t_like.get("day_of_month"), interval_hours=t_like.get("interval_hours"),
        run_at=t_like.get("run_at"), timezone_name=t_like.get("timezone") or settings.SCHEDULER_DEFAULT_TIMEZONE,
    )


def _normalize(d: dict) -> dict:
    """선택한 반복 종류와 무관한 필드는 비워서 일정 해석이 모호하지 않게 한다."""
    keep = {
        "once": {"run_at"},
        "interval": {"interval_hours"},
        "daily": {"schedule_time"},
        "weekdays": {"schedule_time"},
        "weekly": {"schedule_time", "weekdays"},
        "monthly": {"schedule_time", "day_of_month"},
    }[d["schedule_type"]]
    for f in ("schedule_time", "weekdays", "day_of_month", "interval_hours", "run_at"):
        if f not in keep:
            d[f] = None
    return d


class ScheduleService:
    # ── 조회 ────────────────────────────────────────────────────────────────
    @staticmethod
    async def list_tasks(user_id: str, db: AsyncSession) -> list[ScheduledTask]:
        r = await db.execute(select(ScheduledTask).where(ScheduledTask.user_id == user_id).order_by(ScheduledTask.created_at.desc()))
        return list(r.scalars().all())

    @staticmethod
    async def get_task(task_id: str, user_id: str, db: AsyncSession) -> ScheduledTask:
        r = await db.execute(select(ScheduledTask).where(ScheduledTask.id == task_id, ScheduledTask.user_id == user_id))
        t = r.scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=404, detail="예약 작업을 찾을 수 없습니다")
        return t

    @staticmethod
    def run_response(r: TaskRun) -> RunResponse:
        return RunResponse(
            id=r.id, task_id=r.task_id, status=r.status, trigger=r.trigger,
            scheduled_for=aware(r.scheduled_for), started_at=aware(r.started_at), finished_at=aware(r.finished_at),
            conversation_id=r.conversation_id, summary=r.summary, error=r.error,
            unread=r.status in NOTIFY_STATUSES and r.read_at is None,
        )

    @staticmethod
    async def to_responses(tasks: list[ScheduledTask], db: AsyncSession) -> list[TaskResponse]:
        if not tasks:
            return []
        ids = [t.id for t in tasks]
        unread = dict((await db.execute(
            select(TaskRun.task_id, func.count()).where(
                TaskRun.task_id.in_(ids), TaskRun.status.in_(NOTIFY_STATUSES), TaskRun.read_at.is_(None)
            ).group_by(TaskRun.task_id)
        )).all())
        active = {x for (x,) in (await db.execute(
            select(TaskRun.task_id).where(TaskRun.task_id.in_(ids), TaskRun.status.in_(("queued", "running")))
        )).all()}
        from app.models.agent import Agent

        agent_ids = {t.agent_id for t in tasks if t.agent_id}
        agent_names = {}
        if agent_ids:
            agent_names = {a.id: a.name for a in (await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))).scalars().all()}
        out = []
        for t in tasks:
            last = (await db.execute(
                select(TaskRun).where(TaskRun.task_id == t.id).order_by(TaskRun.created_at.desc()).limit(1)
            )).scalars().first()
            out.append(TaskResponse(
                id=t.id, name=t.name, prompt=t.prompt, schedule_type=t.schedule_type, schedule_time=t.schedule_time,
                weekdays=t.weekdays, day_of_month=t.day_of_month, interval_hours=t.interval_hours,
                run_at=aware(t.run_at), timezone=t.timezone,
                schedule_text=calc.describe(t.schedule_type, **_spec(t)),
                status=status_of(t), enabled=t.enabled, running=t.id in active,
                conversation_id=t.conversation_id, new_conversation_each_run=t.new_conversation_each_run,
                allow_mcp=t.allow_mcp, allow_browser=t.allow_browser, llm_provider=t.llm_provider, model_name=t.model_name,
                agent_id=t.agent_id, agent_name=agent_names.get(t.agent_id),
                next_run_at=aware(t.next_run_at), last_run_at=aware(t.last_run_at), last_status=t.last_status,
                consecutive_failures=t.consecutive_failures, unread_count=int(unread.get(t.id, 0)),
                last_run=ScheduleService.run_response(last) if last else None, created_at=aware(t.created_at),
            ))
        return out

    # ── 생성 · 수정 · 삭제 ───────────────────────────────────────────────────
    @staticmethod
    async def create_task(user_id: str, data: TaskInput, db: AsyncSession) -> ScheduledTask:
        count = (await db.execute(select(func.count()).select_from(ScheduledTask).where(ScheduledTask.user_id == user_id))).scalar() or 0
        if count >= settings.SCHEDULER_MAX_TASKS_PER_USER:
            raise HTTPException(status_code=400, detail=f"예약 작업은 최대 {settings.SCHEDULER_MAX_TASKS_PER_USER}개까지 만들 수 있습니다")
        d = _normalize(data.model_dump())
        now = now_utc()
        _validate(d, now)
        t = ScheduledTask(user_id=user_id, **d, enabled=True, next_run_at=_next_run(d, now))
        db.add(t)
        await db.commit()
        await db.refresh(t)
        return t

    @staticmethod
    async def update_task(t: ScheduledTask, data: TaskUpdate, db: AsyncSession) -> ScheduledTask:
        patch = data.model_dump(exclude_unset=True)
        cur = {f: getattr(t, f) for f in SCHEDULE_FIELDS}
        merged = {**cur, **{k: v for k, v in patch.items() if k in SCHEDULE_FIELDS}}
        schedule_changed = any(k in patch for k in SCHEDULE_FIELDS)
        if schedule_changed:
            merged = _normalize(merged)
            now = now_utc()
            # 한 번 실행 작업의 시각은 새로 지정하는 경우에만 '미래' 검사를 한다
            _validate(merged, now)
            for f in SCHEDULE_FIELDS:
                setattr(t, f, merged.get(f))
        for k in ("name", "prompt", "new_conversation_each_run", "allow_mcp", "allow_browser", "llm_provider", "model_name"):
            if k in patch and patch[k] is not None:
                setattr(t, k, patch[k].strip() if isinstance(patch[k], str) else patch[k])
        if "agent_id" in patch:  # 명시적으로 null 을 보내면 기본 에이전트로 되돌린다
            t.agent_id = patch["agent_id"]
        if schedule_changed:
            t.next_run_at = _next_run(merged, now_utc()) if t.enabled else None
            if t.enabled:
                t.last_status = t.last_status if t.last_status != "auto_paused" else None
        await db.commit()
        await db.refresh(t)
        return t

    @staticmethod
    async def set_enabled(t: ScheduledTask, enabled: bool, db: AsyncSession) -> ScheduledTask:
        if enabled:
            spec = {f: getattr(t, f) for f in SCHEDULE_FIELDS}
            if t.schedule_type == "once":
                if t.run_at is None or t.run_at <= now_utc():
                    raise HTTPException(status_code=400, detail="이미 지난 한 번 실행 작업입니다. 수정에서 새 시각을 지정하세요")
            t.enabled = True
            t.consecutive_failures = 0
            if t.last_status == "auto_paused":
                t.last_status = None
            t.next_run_at = _next_run(spec, now_utc())
        else:
            t.enabled = False
            t.next_run_at = None
        await db.commit()
        await db.refresh(t)
        return t

    @staticmethod
    async def delete_task(t: ScheduledTask, db: AsyncSession) -> None:
        # 실행 이력은 삭제하지만 결과가 담긴 대화는 사용자의 기록이므로 남긴다
        await db.execute(delete(TaskRun).where(TaskRun.task_id == t.id))
        await db.delete(t)
        await db.commit()

    # ── 이력 · 읽지 않음 ─────────────────────────────────────────────────────
    @staticmethod
    async def list_runs(task_id: str, user_id: str, db: AsyncSession, limit: int = 50) -> list[TaskRun]:
        r = await db.execute(
            select(TaskRun).where(TaskRun.task_id == task_id, TaskRun.user_id == user_id)
            .order_by(TaskRun.created_at.desc()).limit(limit)
        )
        return list(r.scalars().all())

    @staticmethod
    async def unread_count(user_id: str, db: AsyncSession) -> int:
        return (await db.execute(
            select(func.count()).select_from(TaskRun).where(
                TaskRun.user_id == user_id, TaskRun.status.in_(NOTIFY_STATUSES), TaskRun.read_at.is_(None)
            )
        )).scalar() or 0

    @staticmethod
    async def mark_run_read(run_id: str, user_id: str, db: AsyncSession) -> None:
        await db.execute(
            update(TaskRun).where(TaskRun.id == run_id, TaskRun.user_id == user_id, TaskRun.read_at.is_(None)).values(read_at=now_utc())
        )
        await db.commit()

    @staticmethod
    async def mark_task_read(task_id: str, user_id: str, db: AsyncSession) -> None:
        await db.execute(
            update(TaskRun).where(TaskRun.task_id == task_id, TaskRun.user_id == user_id, TaskRun.read_at.is_(None)).values(read_at=now_utc())
        )
        await db.commit()

    @staticmethod
    async def mark_conversation_read(conversation_id: str, user_id: str, db: AsyncSession) -> None:
        """사용자가 결과 대화를 열면 그 대화의 실행 결과를 읽은 것으로 처리한다."""
        await db.execute(
            update(TaskRun).where(
                TaskRun.conversation_id == conversation_id, TaskRun.user_id == user_id, TaskRun.read_at.is_(None)
            ).values(read_at=now_utc())
        )
        await db.commit()

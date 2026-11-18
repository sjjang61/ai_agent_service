"""Function 트리거: 예약(기존 schedule_calc 재사용)과 웹훅. 모두 소유자의 권한과 쿼터로 실행된다.

- 예약: next_run_at 을 읽은 값과 같을 때만 갱신하는 조건부 UPDATE 로 선점해, 서버 프로세스가 여럿이어도 한 번만 실행한다.
  서버 중단으로 유예 시간(SCHEDULER_MISFIRE_GRACE_SECONDS)보다 늦으면 실행하지 않고 건너뛴다. 연속 실패가 한도에 이르면 자동으로 멈춘다.
- 웹훅: 토큰은 해시만 저장하고 평문은 만들 때 한 번만 돌려준다. 재발급하면 이전 토큰은 즉시 무효가 된다.
"""
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.function import Function, FunctionRun, FunctionTrigger
from app.models.user import User
from app.services import function_service as fsvc
from app.services import schedule_calc as calc
from app.services.function_service import FunctionError

FAIL_STATUSES = ("failed", "timeout", "rejected")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _spec(t: FunctionTrigger) -> dict:
    return dict(schedule_time=t.schedule_time, weekdays=t.weekdays, day_of_month=t.day_of_month, interval_hours=t.interval_hours, run_at=t.run_at, timezone_name=t.timezone or settings.SCHEDULER_DEFAULT_TIMEZONE)


def _next(t: FunctionTrigger, after: datetime) -> Optional[datetime]:
    return calc.compute_next_run(t.schedule_type, after, **_spec(t))


async def _check_new(db: AsyncSession, user, function_id: str, ref: Optional[str]) -> tuple:
    fsvc.require_allowed(user)
    fn = await fsvc.get_function(db, user.id, function_id)
    await fsvc.resolve_version(db, fn, ref)  # 없는 별칭·버전은 만들 때 거부한다
    count = (await db.execute(select(func.count()).select_from(FunctionTrigger).where(FunctionTrigger.user_id == user.id))).scalar() or 0
    if count >= settings.FUNCTION_TRIGGERS_MAX_PER_USER:
        raise FunctionError(400, f"트리거는 사용자당 {settings.FUNCTION_TRIGGERS_MAX_PER_USER}개까지 만들 수 있습니다")
    return fn, (ref or "latest")


async def create_schedule(db: AsyncSession, user, function_id: str, name: str, ref: Optional[str], schedule_type: str, **spec) -> FunctionTrigger:
    fn, ref = await _check_new(db, user, function_id, ref)
    tz = spec.get("timezone_name") or settings.SCHEDULER_DEFAULT_TIMEZONE
    try:
        calc.validate_spec(schedule_type, timezone_name=tz, min_interval_hours=settings.SCHEDULER_MIN_INTERVAL_HOURS, **{k: v for k, v in spec.items() if k != "timezone_name"})
    except calc.ScheduleError as e:
        raise FunctionError(400, str(e))
    t = FunctionTrigger(function_id=fn.id, user_id=user.id, kind="schedule", name=(name or "")[:100], ref=ref, schedule_type=schedule_type, timezone=tz,
                        schedule_time=spec.get("schedule_time"), weekdays=spec.get("weekdays"), day_of_month=spec.get("day_of_month"),
                        interval_hours=spec.get("interval_hours"), run_at=spec.get("run_at"))
    t.next_run_at = _next(t, _now())
    db.add(t)
    await db.commit()
    return t


async def create_webhook(db: AsyncSession, user, function_id: str, name: str, ref: Optional[str]) -> tuple:
    """반환: (트리거, 평문 토큰). 평문은 이 순간에만 알 수 있다."""
    fn, ref = await _check_new(db, user, function_id, ref)
    token = secrets.token_urlsafe(32)
    t = FunctionTrigger(function_id=fn.id, user_id=user.id, kind="webhook", name=(name or "")[:100], ref=ref, token_hash=hash_token(token))
    db.add(t)
    await db.commit()
    return t, token


async def get_trigger(db: AsyncSession, user_id: str, trigger_id: str) -> FunctionTrigger:
    t = await db.get(FunctionTrigger, trigger_id, populate_existing=True)
    if t is None or t.user_id != user_id:
        raise FunctionError(404, "트리거를 찾을 수 없습니다")
    return t


async def list_triggers(db: AsyncSession, user_id: str, function_id: Optional[str] = None) -> list:
    q = select(FunctionTrigger).where(FunctionTrigger.user_id == user_id)
    if function_id:
        q = q.where(FunctionTrigger.function_id == function_id)
    return list((await db.execute(q.order_by(FunctionTrigger.created_at))).scalars().all())


async def set_enabled(db: AsyncSession, user_id: str, trigger_id: str, enabled: bool) -> FunctionTrigger:
    t = await get_trigger(db, user_id, trigger_id)
    t.enabled = enabled
    if t.kind == "schedule":
        t.consecutive_failures = 0 if enabled else t.consecutive_failures
        t.next_run_at = _next(t, _now()) if enabled else t.next_run_at
        if enabled and t.schedule_type == "once" and t.next_run_at is None:
            raise FunctionError(400, "한 번 실행하는 예약의 시각이 이미 지났습니다. 새로 만드세요")
    await db.commit()
    return t


async def regenerate_webhook(db: AsyncSession, user_id: str, trigger_id: str) -> tuple:
    t = await get_trigger(db, user_id, trigger_id)
    if t.kind != "webhook":
        raise FunctionError(400, "웹훅 트리거가 아닙니다")
    token = secrets.token_urlsafe(32)
    t.token_hash = hash_token(token)  # 이전 토큰은 즉시 무효
    await db.commit()
    return t, token


async def delete_trigger(db: AsyncSession, user_id: str, trigger_id: str) -> None:
    t = await get_trigger(db, user_id, trigger_id)
    await db.delete(t)
    await db.commit()


async def _owner(db: AsyncSession, user_id: str) -> Optional[User]:
    return await db.get(User, user_id)


async def fire_webhook(db: AsyncSession, token: str, event) -> FunctionRun:
    """토큰으로 함수를 실행한다. 알 수 없거나 꺼진 토큰은 모두 같은 404 (존재 여부를 알려 주지 않는다)."""
    t = (await db.execute(select(FunctionTrigger).where(FunctionTrigger.token_hash == hash_token(token), FunctionTrigger.kind == "webhook"))).scalar_one_or_none() if token else None
    if t is None or not t.enabled:
        raise FunctionError(404, "존재하지 않거나 비활성화된 웹훅입니다")
    owner = await _owner(db, t.user_id)
    if owner is None or not getattr(owner, "is_active", True):
        raise FunctionError(404, "존재하지 않거나 비활성화된 웹훅입니다")
    t.last_called_at = _now()
    await db.commit()
    try:
        return await fsvc.invoke(db, owner, t.function_id, event, ref=t.ref, trigger="webhook")
    except FunctionError as e:
        if e.status in (403, 503):  # 소유자의 권한·관리자 중지 상태를 토큰 보유자에게 알려 주지 않는다
            raise FunctionError(404, "존재하지 않거나 비활성화된 웹훅입니다")
        raise


async def _refresh_failures(db: AsyncSession, t: FunctionTrigger) -> None:
    """직전 회차의 결과를 보고 연속 실패 수를 갱신한다 (실행이 끝난 뒤 다음 회차가 올 때 반영)."""
    if not t.last_run_id:
        return
    st = (await db.execute(select(FunctionRun.status).where(FunctionRun.id == t.last_run_id))).scalar()
    if st in FAIL_STATUSES:
        t.consecutive_failures = (t.consecutive_failures or 0) + 1
    elif st == "succeeded":
        t.consecutive_failures = 0


async def fire_due_schedules(db: AsyncSession, now: Optional[datetime] = None, limit: int = 50) -> int:
    """실행 시각이 된 예약을 선점해 큐에 넣는다. 반환: 큐에 넣은 실행 수."""
    now = now or _now()
    due = (await db.execute(select(FunctionTrigger).where(FunctionTrigger.kind == "schedule", FunctionTrigger.enabled.is_(True), FunctionTrigger.next_run_at.is_not(None),
                                                         FunctionTrigger.next_run_at <= now).order_by(FunctionTrigger.next_run_at).limit(limit))).scalars().all()
    fired = 0
    grace = settings.SCHEDULER_MISFIRE_GRACE_SECONDS
    for t in due:
        old = t.next_run_at
        late = (now - old).total_seconds()
        nxt = _next(t, now)
        r = await db.execute(update(FunctionTrigger).where(FunctionTrigger.id == t.id, FunctionTrigger.next_run_at == old).values(next_run_at=nxt))
        await db.commit()
        if (r.rowcount or 0) != 1:
            continue  # 다른 프로세스가 먼저 선점했다
        t = await db.get(FunctionTrigger, t.id, populate_existing=True)
        if late > grace:
            t.last_status = f"건너뜀: 예정보다 {int(late // 60)}분 늦음"
            await db.commit()
            continue
        await _refresh_failures(db, t)
        if t.consecutive_failures >= settings.SCHEDULER_MAX_CONSECUTIVE_FAILURES:
            t.enabled, t.last_status = False, f"연속 {t.consecutive_failures}회 실패해 자동으로 멈췄습니다"
            await db.commit()
            continue
        owner = await _owner(db, t.user_id)
        try:
            if owner is None:
                raise FunctionError(404, "소유자를 찾을 수 없습니다")
            run = await fsvc.invoke(db, owner, t.function_id, {}, ref=t.ref, trigger="schedule")
            t.last_run_id, t.last_status = run.id, "queued"
            fired += 1
        except FunctionError as e:
            t.last_run_id, t.last_status = None, f"실행하지 못함: {e.message}"[:120]
            t.consecutive_failures = (t.consecutive_failures or 0) + 1
        t.last_run_at = now
        if nxt is None:
            t.enabled = False  # 한 번 실행하는 예약은 끝났다
        await db.commit()
    return fired


STATUS_KO = {"queued": "대기 중", "starting": "시작 중", "running": "실행 중", "succeeded": "성공", "failed": "실패", "timeout": "시간 초과", "cancelled": "취소됨", "rejected": "거부됨"}


async def run_statuses(db: AsyncSession, triggers: list) -> dict:
    """트리거가 마지막으로 만든 실행의 현재 상태 {run_id: status}. 트리거 행의 last_status 는 실행을 큐에 넣은 시점의 값이라 끝난 뒤에는 오래된 값이 된다."""
    ids = [t.last_run_id for t in triggers if t.last_run_id]
    if not ids:
        return {}
    rows = (await db.execute(select(FunctionRun.id, FunctionRun.status).where(FunctionRun.id.in_(ids)))).all()
    return {rid: st for rid, st in rows}


def trigger_dict(t: FunctionTrigger, token: Optional[str] = None, run_status: Optional[str] = None) -> dict:
    d = {
        "id": t.id, "function_id": t.function_id, "kind": t.kind, "name": t.name, "ref": t.ref, "enabled": bool(t.enabled),
        "last_run_at": t.last_run_at.isoformat() if t.last_run_at else None, "last_run_id": t.last_run_id,
        "last_status": f"마지막 실행 {STATUS_KO.get(run_status, run_status)}" if run_status else t.last_status,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }
    if t.kind == "schedule":
        d.update({
            "schedule_type": t.schedule_type, "schedule_time": t.schedule_time, "weekdays": t.weekdays, "day_of_month": t.day_of_month, "interval_hours": t.interval_hours,
            "timezone": t.timezone, "next_run_at": t.next_run_at.isoformat() if t.next_run_at else None, "consecutive_failures": t.consecutive_failures,
            "description": calc.describe(t.schedule_type, schedule_time=t.schedule_time, weekdays=t.weekdays, day_of_month=t.day_of_month, interval_hours=t.interval_hours, timezone_name=t.timezone or ""),
        })
    else:
        d.update({"last_called_at": t.last_called_at.isoformat() if t.last_called_at else None, "path": f"/api/fn-hooks/{token}" if token else None})
    return d

"""예약 작업의 반복 일정 계산 (순수 함수 — DB 에 의존하지 않는다).

모든 시각 입출력은 UTC naive datetime 이다. 반복은 현지 시각과 IANA 시간대로 해석해서 서머타임이 있는 지역도 맞춘다.
"""
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEDULE_TYPES = ("once", "interval", "daily", "weekdays", "weekly", "monthly")
UTC = timezone.utc


class ScheduleError(ValueError):
    """사용자 입력(일정)이 올바르지 않을 때."""


def get_tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        raise ScheduleError(f"알 수 없는 시간대입니다: {name}")


def parse_hhmm(value: Optional[str]) -> time:
    try:
        h, m = (value or "").split(":")
        return time(int(h), int(m))
    except Exception:
        raise ScheduleError("시각은 HH:MM 형식이어야 합니다")


def _localize(d: date, t: time, tz: ZoneInfo) -> datetime:
    """현지 날짜+시각 → tz-aware datetime. 서머타임으로 존재하지 않는 시각은 이후 시각으로 밀린다."""
    dt = datetime.combine(d, t, tzinfo=tz)
    back = dt.astimezone(UTC).astimezone(tz)
    return back if back.replace(tzinfo=None) != dt.replace(tzinfo=None) else dt


def _to_utc_naive(dt: datetime) -> datetime:
    return dt.astimezone(UTC).replace(tzinfo=None)


def _last_day(year: int, month: int) -> int:
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    return (nxt - timedelta(days=1)).day


def validate_spec(
    schedule_type: str,
    *,
    schedule_time: Optional[str] = None,
    weekdays: Optional[list] = None,
    day_of_month: Optional[int] = None,
    interval_hours: Optional[int] = None,
    run_at: Optional[datetime] = None,
    timezone_name: str = "Asia/Seoul",
    min_interval_hours: int = 1,
    now: Optional[datetime] = None,
) -> None:
    if schedule_type not in SCHEDULE_TYPES:
        raise ScheduleError(f"반복 종류는 {', '.join(SCHEDULE_TYPES)} 중 하나여야 합니다")
    get_tz(timezone_name)
    now = now or datetime.now(UTC).replace(tzinfo=None)
    if schedule_type == "once":
        if run_at is None:
            raise ScheduleError("실행할 날짜와 시각이 필요합니다")
        if run_at <= now:
            raise ScheduleError("실행 시각은 현재보다 이후여야 합니다")
    elif schedule_type == "interval":
        if not interval_hours or interval_hours < min_interval_hours or interval_hours > 24 * 7:
            raise ScheduleError(f"반복 간격은 {min_interval_hours}~{24 * 7}시간이어야 합니다")
    else:
        parse_hhmm(schedule_time)
        if schedule_type == "weekly":
            if not weekdays or any((not isinstance(d, int)) or d < 0 or d > 6 for d in weekdays):
                raise ScheduleError("요일을 하나 이상 선택하세요 (0=월 … 6=일)")
        if schedule_type == "monthly":
            if not day_of_month or not 1 <= day_of_month <= 31:
                raise ScheduleError("일자는 1~31 이어야 합니다")


def compute_next_run(
    schedule_type: str,
    after: datetime,
    *,
    schedule_time: Optional[str] = None,
    weekdays: Optional[list] = None,
    day_of_month: Optional[int] = None,
    interval_hours: Optional[int] = None,
    run_at: Optional[datetime] = None,
    timezone_name: str = "Asia/Seoul",
) -> Optional[datetime]:
    """`after` (UTC naive) 이후의 가장 이른 실행 시각(UTC naive). 더 이상 없으면 None (한 번 실행 후)."""
    if schedule_type == "once":
        return run_at if run_at and run_at > after else None
    if schedule_type == "interval":
        return after + timedelta(hours=int(interval_hours or 1))

    tz = get_tz(timezone_name)
    t = parse_hhmm(schedule_time)
    local_after = after.replace(tzinfo=UTC).astimezone(tz)
    start = local_after.date()

    for offset in range(0, 400):  # 월간(최대 ~31일)과 주간(7일) 모두 충분히 덮는다
        d = start + timedelta(days=offset)
        if schedule_type == "weekdays" and d.weekday() >= 5:
            continue
        if schedule_type == "weekly" and d.weekday() not in (weekdays or []):
            continue
        if schedule_type == "monthly" and d.day != min(int(day_of_month or 1), _last_day(d.year, d.month)):
            continue
        cand = _localize(d, t, tz)
        if _to_utc_naive(cand) > after:
            return _to_utc_naive(cand)
    return None


def describe(
    schedule_type: str,
    *,
    schedule_time: Optional[str] = None,
    weekdays: Optional[list] = None,
    day_of_month: Optional[int] = None,
    interval_hours: Optional[int] = None,
    timezone_name: str = "Asia/Seoul",
    **_,
) -> str:
    names = "월화수목금토일"
    if schedule_type == "once":
        return "한 번 실행"
    if schedule_type == "interval":
        return f"{interval_hours}시간마다"
    when = f"{schedule_time} ({timezone_name})"
    if schedule_type == "daily":
        return f"매일 {when}"
    if schedule_type == "weekdays":
        return f"평일 {when}"
    if schedule_type == "weekly":
        return f"매주 {'·'.join(names[d] for d in sorted(weekdays or []))}요일 {when}"
    return f"매월 {day_of_month}일 {when}"

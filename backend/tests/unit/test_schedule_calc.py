from datetime import date, datetime, timedelta

import pytest

from app.services.schedule_calc import ScheduleError, compute_next_run, describe, validate_spec

KST = "Asia/Seoul"


def utc(y, mo, d, h=0, mi=0):
    return datetime(y, mo, d, h, mi)  # UTC naive


def test_daily_before_and_after_time():
    # 09:00 KST == 00:00 UTC
    assert compute_next_run("daily", utc(2026, 10, 18, 23, 59), schedule_time="09:00", timezone_name=KST) == utc(2026, 10, 19, 0, 0)
    # 정확히 그 시각이면 다음 날 (현재 시각은 '이후'가 아니다)
    assert compute_next_run("daily", utc(2026, 10, 19, 0, 0), schedule_time="09:00", timezone_name=KST) == utc(2026, 10, 20, 0, 0)


def test_weekdays_skips_weekend():
    assert date(2026, 10, 23).weekday() == 4  # 금요일
    nxt = compute_next_run("weekdays", utc(2026, 10, 23, 0, 0), schedule_time="09:00", timezone_name=KST)
    assert nxt == utc(2026, 10, 26, 0, 0)  # 월요일
    assert date(2026, 10, 26).weekday() == 0


def test_weekly_picks_next_selected_day():
    # 월(0)·목(3). 월요일 09:00 이후 → 목요일
    nxt = compute_next_run("weekly", utc(2026, 10, 26, 0, 0), schedule_time="09:00", weekdays=[0, 3], timezone_name=KST)
    assert nxt == utc(2026, 10, 29, 0, 0)
    assert date(2026, 10, 29).weekday() == 3


def test_monthly_clamps_to_last_day():
    spec = dict(schedule_time="09:00", day_of_month=31, timezone_name=KST)
    assert compute_next_run("monthly", utc(2026, 2, 1), **spec) == utc(2026, 2, 28, 0, 0)  # 평년 2월
    assert compute_next_run("monthly", utc(2028, 2, 1), **spec) == utc(2028, 2, 29, 0, 0)  # 윤년 2월
    assert compute_next_run("monthly", utc(2026, 2, 28, 0, 0), **spec) == utc(2026, 3, 31, 0, 0)
    assert compute_next_run("monthly", utc(2026, 4, 1), **spec) == utc(2026, 4, 30, 0, 0)  # 4월은 30일


def test_monthly_crosses_year_end():
    assert compute_next_run("monthly", utc(2026, 12, 31, 0, 0), schedule_time="09:00", day_of_month=15, timezone_name=KST) == utc(2027, 1, 15, 0, 0)


def test_interval_and_once():
    assert compute_next_run("interval", utc(2026, 10, 19, 5, 0), interval_hours=6) == utc(2026, 10, 19, 11, 0)
    run_at = utc(2026, 10, 20, 3, 0)
    assert compute_next_run("once", utc(2026, 10, 19), run_at=run_at) == run_at
    assert compute_next_run("once", run_at, run_at=run_at) is None  # 이미 지남


def test_dst_nonexistent_local_time_moves_forward():
    # 2026-03-08 02:30 America/New_York 는 존재하지 않는다 (02:00 → 03:00 점프) → 03:30 EDT = 07:30 UTC
    nxt = compute_next_run("daily", utc(2026, 3, 8, 0, 0), schedule_time="02:30", timezone_name="America/New_York")
    assert nxt == utc(2026, 3, 8, 7, 30)
    # 다음 날은 정상(EDT 02:30 = 06:30 UTC)
    assert compute_next_run("daily", nxt, schedule_time="02:30", timezone_name="America/New_York") == utc(2026, 3, 9, 6, 30)


def test_dst_ambiguous_local_time_uses_first_occurrence():
    # 2026-11-01 01:30 은 두 번 존재 → 첫 번째(EDT, UTC-4) = 05:30 UTC
    nxt = compute_next_run("daily", utc(2026, 11, 1, 0, 0), schedule_time="01:30", timezone_name="America/New_York")
    assert nxt == utc(2026, 11, 1, 5, 30)


def test_wall_clock_is_stable_across_dst_change():
    # 현지 09:00 을 유지한다: 서머타임 전(EST, UTC-5)은 14:00 UTC, 전환 후(EDT, UTC-4)는 13:00 UTC
    before = compute_next_run("daily", utc(2026, 3, 7, 12, 0), schedule_time="09:00", timezone_name="America/New_York")
    after = compute_next_run("daily", utc(2026, 3, 8, 12, 0), schedule_time="09:00", timezone_name="America/New_York")
    assert before == utc(2026, 3, 7, 14, 0)
    assert after == utc(2026, 3, 8, 13, 0)


NOW = datetime(2026, 10, 19, 0, 0)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(schedule_type="hourly"),
        dict(schedule_type="daily", schedule_time="9시"),
        dict(schedule_type="daily", schedule_time="09:00", timezone_name="Mars/Base"),
        dict(schedule_type="weekly", schedule_time="09:00", weekdays=[]),
        dict(schedule_type="weekly", schedule_time="09:00", weekdays=[7]),
        dict(schedule_type="monthly", schedule_time="09:00", day_of_month=0),
        dict(schedule_type="monthly", schedule_time="09:00", day_of_month=32),
        dict(schedule_type="interval", interval_hours=0),
        dict(schedule_type="interval", interval_hours=24 * 7 + 1),
        dict(schedule_type="once"),
        dict(schedule_type="once", run_at=NOW - timedelta(minutes=1)),
    ],
)
def test_validate_rejects_bad_specs(kwargs):
    with pytest.raises(ScheduleError):
        validate_spec(now=NOW, **kwargs)


def test_validate_accepts_good_specs():
    validate_spec("daily", schedule_time="09:00", now=NOW)
    validate_spec("weekly", schedule_time="18:30", weekdays=[0, 4], now=NOW)
    validate_spec("monthly", schedule_time="09:00", day_of_month=31, now=NOW)
    validate_spec("interval", interval_hours=1, now=NOW)
    validate_spec("once", run_at=NOW + timedelta(minutes=5), now=NOW)


def test_describe_korean():
    assert describe("daily", schedule_time="09:00", timezone_name=KST) == "매일 09:00 (Asia/Seoul)"
    assert describe("weekly", schedule_time="09:00", weekdays=[0, 4], timezone_name=KST) == "매주 월·금요일 09:00 (Asia/Seoul)"
    assert describe("interval", interval_hours=3) == "3시간마다"
    assert describe("once") == "한 번 실행"

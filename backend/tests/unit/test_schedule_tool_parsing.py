from datetime import datetime

import pytest

from app.tools.schedule_tool import parse_local_datetime, parse_weekdays


def test_parse_weekdays_accepts_korean_english_and_numbers():
    assert parse_weekdays("월,금") == [0, 4]
    assert parse_weekdays("Mon, fri") == [0, 4]
    assert parse_weekdays("월요일 · 수요일") == [0, 2]
    assert parse_weekdays("0,6,6") == [0, 6]  # 중복 제거
    assert parse_weekdays(None) is None
    assert parse_weekdays("") == []


def test_parse_weekdays_rejects_unknown_tokens():
    with pytest.raises(ValueError):
        parse_weekdays("월,xyz")
    with pytest.raises(ValueError):
        parse_weekdays("7")


def test_parse_local_datetime_converts_to_utc_naive():
    # 서울(UTC+9) 18:30 → 09:30 UTC
    assert parse_local_datetime("2026-10-20 18:30", "Asia/Seoul") == datetime(2026, 10, 20, 9, 30)
    assert parse_local_datetime("2026-10-20T18:30", "Asia/Seoul") == datetime(2026, 10, 20, 9, 30)
    # 이미 시간대가 있는 값은 그대로 변환
    assert parse_local_datetime("2026-10-20T18:30+00:00", "Asia/Seoul") == datetime(2026, 10, 20, 18, 30)


def test_parse_local_datetime_rejects_garbage():
    with pytest.raises(ValueError):
        parse_local_datetime("내일 아침", "Asia/Seoul")

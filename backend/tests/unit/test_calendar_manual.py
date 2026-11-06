import pytest
from pydantic import ValidationError

from app.api.calendar import EventInput, _expires, _memory_text


def test_input_defaults_end_date():
    e = EventInput(title=" 치과  예약 ", start_date="2026-12-01", start_time="14:30")
    assert e.end_date == "2026-12-01" and e.title == "치과 예약"


@pytest.mark.parametrize("kw", [{"start_date": "2026-13-01"}, {"start_date": "2026-12-05", "end_date": "2026-12-01"}, {"start_date": "2026-12-01", "start_time": "25:00"}])
def test_input_rejects(kw):
    with pytest.raises(ValidationError):
        EventInput(title="x", **kw)


def test_memory_text_and_expiry():
    e = EventInput(title="오사카 여행", start_date="2026-12-03", end_date="2026-12-09", note="성인2")
    assert _memory_text(e) == "오사카 여행 (2026-12-03~2026-12-09) - 성인2"
    assert _expires("2026-12-09").isoformat().startswith("2026-12-09T15:00")  # KST 12/10 00:00

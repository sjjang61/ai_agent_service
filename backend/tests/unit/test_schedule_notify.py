"""예약 작업의 조건부 알림: 규칙 문구, [NO_ALERT] 해석, 알림 여부 판단, 입력 검증."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.schemas.schedule import TaskInput
from app.services import task_runner as tr
from app.services.schedule_service import ScheduleService


def task(mode="always", cond=None, last=None):
    return SimpleNamespace(notify_mode=mode, notify_condition=cond, last_result=last)


def test_split_no_alert_detects_marker_on_first_line_only():
    assert tr.split_no_alert("[NO_ALERT]\n해당 일정이 없습니다") == ("해당 일정이 없습니다", True)
    assert tr.split_no_alert("  [no_alert] 변화 없음") == ("변화 없음", True)
    assert tr.split_no_alert("[NO_ALERT]") == ("알림 조건에 해당하지 않습니다", True)
    text = "오늘 일정입니다.\n[NO_ALERT] 라고 쓰면 안 됩니다"
    assert tr.split_no_alert(text) == (text, False)  # 본문 중간의 표시는 무시
    assert tr.split_no_alert("") == ("", False)


def test_notify_rules_per_mode():
    assert tr.notify_rules(task("always")) == "" and tr.notify_rules(task("on_failure")) == ""
    r = tr.notify_rules(task("on_condition", "2시간 안에 시작하는 일정"))
    assert "2시간 안에 시작하는 일정" in r and "[NO_ALERT]" in r
    assert tr.notify_rules(task("on_condition", "  ")) == ""  # 조건이 비면 규칙 없음(항상 알림)
    assert tr.notify_rules(task("on_change", last=None)) == ""  # 첫 실행은 비교 대상이 없다
    r = tr.notify_rules(task("on_change", last="매출 100"))
    assert "매출 100" in r and "[NO_ALERT]" in r
    assert len(tr.notify_rules(task("on_change", last="가" * 9000))) < 6000  # 직전 결과는 잘라서 붙인다


@pytest.mark.parametrize("mode,status,no_alert,trigger,expected", [
    ("always", "succeeded", False, "schedule", True),
    ("on_failure", "succeeded", False, "schedule", False),  # 성공은 조용히
    ("on_failure", "failed", False, "schedule", True),
    ("on_condition", "succeeded", True, "schedule", False),
    ("on_condition", "succeeded", False, "schedule", True),
    ("on_change", "succeeded", True, "schedule", False),
    ("on_condition", "failed", True, "schedule", True),  # 실패는 방식과 무관하게 알린다
    ("on_condition", "succeeded", True, "manual", True),  # 수동 실행은 사용자가 직접 본다
    (None, "succeeded", False, "schedule", True),  # 기존 행(모드 없음)은 항상 알림
])
def test_should_notify(mode, status, no_alert, trigger, expected):
    assert tr.should_notify(task(mode), status, no_alert, trigger) is expected


def test_task_input_defaults_and_rejects_unknown_mode():
    base = dict(name="n", prompt="p", schedule_type="daily", schedule_time="09:00")
    assert TaskInput(**base).notify_mode == "always"
    with pytest.raises(Exception):
        TaskInput(**base, notify_mode="sometimes")


class _CountDb:
    async def execute(self, *a, **k):
        return SimpleNamespace(scalar=lambda: 0)


@pytest.mark.asyncio
async def test_create_requires_condition_for_on_condition():
    data = TaskInput(name="n", prompt="p", schedule_type="daily", schedule_time="09:00", notify_mode="on_condition", notify_condition="  ")
    with pytest.raises(HTTPException) as e:
        await ScheduleService.create_task("u1", data, db=_CountDb())
    assert e.value.status_code == 400 and "알림 조건" in e.value.detail

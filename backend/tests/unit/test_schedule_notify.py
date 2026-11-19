"""예약 작업의 조건부 알림: 규칙 문구, [NO_ALERT] 해석, 알림 여부 판단, 입력 검증."""
import asyncio
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


# ---- 예약 실행 결과 답변의 후속 질문(발화 가이드) 2개 ----
def _task(prompt="매일 아침 일정을 알려줘"):
    from types import SimpleNamespace

    return SimpleNamespace(prompt=prompt)


@pytest.mark.asyncio
async def test_successful_run_gets_two_followup_suggestions_in_background(monkeypatch):
    from app.services import followup_service as fs
    from app.services.task_runner import maybe_suggest_followups

    calls = []

    async def fake_suggest(question, answer):
        calls.append((question, answer))
        return ["내일 일정도 알려줘", "중요한 일정만 따로 정리해줘"]

    saved = {}

    class _Msg:
        def __init__(self):
            self.metadata_ = {"usage": {"x": 1}}

    msg = _Msg()

    class _Db:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, model, mid):
            saved["id"] = mid
            return msg

        async def commit(self):
            saved["committed"] = True

    import app.db.session as dbs

    monkeypatch.setattr(fs, "suggest_followups", fake_suggest)
    monkeypatch.setattr(dbs, "AsyncSessionLocal", lambda: _Db())
    assert maybe_suggest_followups(_task(), "msg-1", "오늘 일정: 10시 회의", "succeeded", False) is True
    await asyncio.gather(*fs._pending)  # 백그라운드 작업이 끝날 때까지
    assert calls == [("매일 아침 일정을 알려줘", "오늘 일정: 10시 회의")]  # 질문은 예약한 작업 내용, 답변은 결과
    assert saved == {"id": "msg-1", "committed": True}
    assert msg.metadata_["suggestions"] == ["내일 일정도 알려줘", "중요한 일정만 따로 정리해줘"]
    assert msg.metadata_["usage"] == {"x": 1}  # 기존 메타데이터는 유지한다


def test_followups_are_skipped_when_not_worth_the_llm_call(monkeypatch):
    from app.config import settings
    from app.services import followup_service as fs
    from app.services.task_runner import maybe_suggest_followups

    started = []
    monkeypatch.setattr(fs, "schedule_attach", lambda *a: started.append(a))
    t = _task()
    assert maybe_suggest_followups(t, "m", "결과", "failed", False) is False  # 실패
    assert maybe_suggest_followups(t, "m", "결과", "cancelled", False) is False  # 취소
    assert maybe_suggest_followups(t, "m", "결과", "succeeded", True) is False  # 조건에 해당하지 않아 알리지 않은 실행
    assert maybe_suggest_followups(t, "m", "   ", "succeeded", False) is False  # 빈 답변
    monkeypatch.setattr(settings, "ENABLE_FOLLOWUP_SUGGESTIONS", False)
    assert maybe_suggest_followups(t, "m", "결과", "succeeded", False) is False  # 기능을 꺼 둔 경우
    assert started == []


@pytest.mark.asyncio
async def test_attach_suggestions_is_silent_when_nothing_to_save(monkeypatch):
    from app.services import followup_service as fs

    async def none(question, answer):
        return []

    monkeypatch.setattr(fs, "suggest_followups", none)
    assert await fs.attach_suggestions("m", "q", "a") == []  # 답변이 오류·사과뿐이라 빈 배열이면 저장하지 않는다

    async def two(question, answer):
        return ["a", "b"]

    class _NoMsgDb:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, model, mid):
            return None  # 사용자가 그 사이 대화를 지운 경우

    import app.db.session as dbs

    monkeypatch.setattr(fs, "suggest_followups", two)
    monkeypatch.setattr(dbs, "AsyncSessionLocal", lambda: _NoMsgDb())
    assert await fs.attach_suggestions("gone", "q", "a") == []

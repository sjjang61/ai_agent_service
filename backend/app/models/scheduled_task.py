import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from app.db.base import Base


def _now():
    return datetime.now(timezone.utc)


class ScheduledTask(Base):
    """예약 작업: '프롬프트 + 반복 일정'. 시각이 되면 사용자 없이 에이전트를 실행한다.

    시각은 DB 에 UTC naive 로 저장한다 (다른 모델과 동일). 반복은 현지 시각(schedule_time)과 IANA 시간대로 해석한다.
    """

    __tablename__ = "scheduled_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    prompt = Column(Text, nullable=False)

    # once | interval | daily | weekdays | weekly | monthly
    schedule_type = Column(String(20), nullable=False)
    schedule_time = Column(String(5), nullable=True)  # "HH:MM" (현지 시각)
    weekdays = Column(JSON, nullable=True)  # weekly: [0..6] (0=월)
    day_of_month = Column(Integer, nullable=True)  # monthly: 1~31 (짧은 달은 말일로 보정)
    interval_hours = Column(Integer, nullable=True)  # interval
    run_at = Column(DateTime, nullable=True)  # once (UTC naive)
    timezone = Column(String(64), nullable=False, default="Asia/Seoul")

    enabled = Column(Boolean, nullable=False, default=True)
    # 결과가 쌓이는 대화. FK 를 두지 않는다: 사용자가 대화를 지워도 작업이 막히지 않고 다음 실행에서 새로 만든다.
    conversation_id = Column(String(36), nullable=True)
    new_conversation_each_run = Column(Boolean, nullable=False, default=False)
    allow_mcp = Column(Boolean, nullable=False, default=False)
    allow_browser = Column(Boolean, nullable=False, default=False)
    llm_provider = Column(String(50), nullable=True)
    model_name = Column(String(100), nullable=True)
    agent_id = Column(String(36), nullable=True)  # 지정하면 이 에이전트의 발행 버전으로 실행

    next_run_at = Column(DateTime, nullable=True, index=True)  # None: 예정 없음(완료/일시중지)
    last_run_at = Column(DateTime, nullable=True)
    last_status = Column(String(30), nullable=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class TaskRun(Base):
    __tablename__ = "task_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("scheduled_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    # queued | running | succeeded | failed | cancelled | skipped
    status = Column(String(20), nullable=False, default="queued")
    trigger = Column(String(20), nullable=False, default="schedule")  # schedule | manual
    scheduled_for = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    conversation_id = Column(String(36), nullable=True)
    summary = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    read_at = Column(DateTime, nullable=True)  # 결과를 확인한 시각 (None 이면 읽지 않음)
    created_at = Column(DateTime, default=_now)

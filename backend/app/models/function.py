import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects import mysql

from app.db.base import Base

# MySQL 의 TEXT 는 64KB 라서 이벤트·결과·로그(최대 1MB)는 MEDIUMTEXT(16MB)로 둔다
LongText = Text().with_variant(mysql.MEDIUMTEXT(), "mysql")


def _now():
    return datetime.now(timezone.utc)


class Function(Base):
    """이름 있는 실행 단위(Lambda 의 함수). 코드는 불변 버전(FunctionVersion)으로 쌓인다."""

    __tablename__ = "functions"
    __table_args__ = (UniqueConstraint("user_id", "name", "deleted_key", name="uq_functions_name"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(64), nullable=False)
    description = Column(String(500), nullable=False, default="")
    runtime = Column(String(20), nullable=False)  # python3.12 | bun (생성 뒤 바꾸지 않는다)
    latest_version = Column(Integer, nullable=False, default=0)
    disabled = Column(Boolean, nullable=False, default=False)  # 관리자 즉시 중지 스위치
    disabled_reason = Column(String(255), nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_key = Column(String(36), nullable=False, default="")  # 살아 있으면 '', 삭제되면 id → 삭제된 이름을 다시 쓸 수 있다
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class FunctionVersion(Base):
    __tablename__ = "function_versions"
    __table_args__ = (UniqueConstraint("function_id", "version", name="uq_function_versions"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    function_id = Column(String(36), ForeignKey("functions.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)  # 원본 zip 의 해시 (같은 내용은 새 버전을 만들지 않는다)
    storage_key = Column(String(255), nullable=False)  # 검증·정규화한 실행용 tar.gz
    size_bytes = Column(BigInteger, nullable=False, default=0)  # tar.gz 크기
    tar_bytes = Column(BigInteger, nullable=False, default=0)  # 압축을 푼 tar 길이 (stdin 프로토콜에 쓴다)
    unpacked_bytes = Column(BigInteger, nullable=False, default=0)  # 파일 내용 합계 (tmpfs 크기 계산)
    file_count = Column(Integer, nullable=False, default=0)
    config = Column(JSON, nullable=False)  # 정규화한 function.json: handler, timeout_seconds, memory_mb, allow_network, env
    source = Column(String(20), nullable=False, default="drive")  # drive | agent
    source_ref = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_now)


class FunctionAlias(Base):
    """사용자 지정 별칭(prod 등) → 버전. 'latest' 는 별칭 행 없이 functions.latest_version 으로 해석한다."""

    __tablename__ = "function_aliases"

    function_id = Column(String(36), ForeignKey("functions.id"), primary_key=True)
    alias = Column(String(40), primary_key=True)
    version = Column(Integer, nullable=False)


class FunctionSecret(Base):
    """실행 시점에 환경변수로만 주입되는 비밀값. 값은 Fernet 으로 암호화하고 조회 API 는 키 이름만 돌려준다."""

    __tablename__ = "function_secrets"

    function_id = Column(String(36), ForeignKey("functions.id"), primary_key=True)
    key = Column(String(64), primary_key=True)
    value_enc = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class FunctionRun(Base):
    """실행 1회의 기록(감사 로그를 겸한다). 큰 열(input/result/log)은 목록 조회에서 읽지 않는다."""

    __tablename__ = "function_runs"
    __table_args__ = (
        Index("ix_function_runs_user_queued", "user_id", "queued_at"),
        Index("ix_function_runs_function_queued", "function_id", "queued_at"),
        Index("ix_function_runs_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    function_id = Column(String(36), ForeignKey("functions.id"), nullable=False)
    version = Column(Integer, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    trigger = Column(String(20), nullable=False, default="manual")  # manual | api | schedule | webhook | agent
    status = Column(String(20), nullable=False, default="queued")  # queued starting running succeeded failed timeout cancelled rejected
    input = Column(LongText, nullable=True)  # JSON 문자열
    result = Column(LongText, nullable=True)  # JSON 문자열
    error = Column(JSON, nullable=True)  # {type, message}
    exit_code = Column(Integer, nullable=True)
    log = Column(LongText, nullable=True)
    log_truncated = Column(Boolean, nullable=False, default=False)
    queued_at = Column(DateTime, default=_now)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    cold_start_ms = Column(Integer, nullable=True)
    attempt = Column(Integer, nullable=False, default=1)
    parent_run_id = Column(String(36), nullable=True)
    cancel_requested = Column(Boolean, nullable=False, default=False)
    idempotency_key = Column(String(80), nullable=True)
    worker_id = Column(String(80), nullable=True)  # 이 실행을 맡은 서버 프로세스 (재시작 복구에 쓴다)


class FunctionTrigger(Base):
    """함수를 자동으로 실행하는 방법: 예약(schedule, 기존 예약 계산기를 재사용)과 웹훅(webhook, 토큰 주소로 호출).
    트리거는 별칭 또는 고정 버전(ref)을 가리킨다 → 새 버전이 나와도 의도치 않게 바뀌지 않는다.
    웹훅 토큰은 해시만 저장하고 평문은 만들 때 한 번만 보여 준다."""

    __tablename__ = "function_triggers"
    __table_args__ = (Index("ix_function_triggers_due", "kind", "enabled", "next_run_at"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    function_id = Column(String(36), ForeignKey("functions.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    kind = Column(String(10), nullable=False)  # schedule | webhook
    name = Column(String(100), nullable=False, default="")
    ref = Column(String(40), nullable=False, default="latest")  # 별칭 또는 버전 번호 (기본 latest)
    enabled = Column(Boolean, nullable=False, default=True)
    # 예약
    schedule_type = Column(String(20), nullable=True)
    schedule_time = Column(String(5), nullable=True)
    weekdays = Column(JSON, nullable=True)
    day_of_month = Column(Integer, nullable=True)
    interval_hours = Column(Integer, nullable=True)
    run_at = Column(DateTime, nullable=True)
    timezone = Column(String(64), nullable=True)
    next_run_at = Column(DateTime, nullable=True)  # None: 예정 없음(완료·일시중지)
    last_run_at = Column(DateTime, nullable=True)
    last_run_id = Column(String(36), nullable=True)
    last_status = Column(String(120), nullable=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    # 웹훅
    token_hash = Column(String(64), nullable=True, unique=True)
    last_called_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

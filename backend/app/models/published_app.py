import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from app.db.base import Base


class PublishedApp(Base):
    """배포된 웹앱. 불변 아카이브(호스트 디스크) + 앱 전용 컨테이너(요청 시 깨움) + 프록시 포트(20000번대)."""

    __tablename__ = "published_apps"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_published_app_user_name"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(String(36), nullable=True)
    name = Column(String(60), nullable=False)
    kind = Column(String(10), nullable=False, default="static")  # static | server
    proxy_port = Column(Integer, nullable=True, unique=True)  # 외부(프록시) 포트
    container_port = Column(Integer, nullable=False, default=5173)
    version = Column(Integer, nullable=False, default=1)
    artifact_size = Column(Integer, nullable=False, default=0)
    status = Column(String(10), nullable=False, default="stopped")  # stopped | starting | running | failed
    error = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    require_token = Column(Boolean, nullable=False, default=False)
    access_token = Column(String(64), nullable=False)
    container_id = Column(String(80), nullable=True)
    last_request_at = Column(DateTime, nullable=True)
    last_log = Column(Text, nullable=True)  # 컨테이너를 내릴 때 남기는 마지막 로그
    # 접근 제어: private(소유자만, 실행 티켓으로 접속) | public(App Store 등록, 호스트명 {slug}.도메인 으로 누구나)
    visibility = Column(String(10), nullable=False, default="private", index=True)
    slug = Column(String(70), nullable=True, unique=True)  # 공개 호스트명 라벨
    session_epoch = Column(Integer, nullable=False, default=0)  # 올리면 발급된 모든 소유자 세션 쿠키가 무효가 된다
    # 공개 앱 검수 상태: approved(서비스 중) | pending(승인 대기) | rejected | suspended(신고로 정지). 비공개 앱은 ''
    moderation_status = Column(String(12), nullable=False, default="")
    moderation_note = Column(Text, nullable=True)
    title = Column(String(100), nullable=True)  # 스토어 표시 제목
    description = Column(Text, nullable=True)
    category = Column(String(30), nullable=True)
    tags = Column(JSON, nullable=True)
    listed_at = Column(DateTime, nullable=True)
    launch_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AppReport(Base):
    """공개 앱 신고. 서로 다른 사용자의 신고가 임계치에 이르면 앱이 자동 정지된다."""

    __tablename__ = "app_reports"
    __table_args__ = (UniqueConstraint("app_id", "reporter_id", name="uq_app_report"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    app_id = Column(String(36), nullable=False, index=True)
    reporter_id = Column(String(36), nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

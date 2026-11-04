import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint

from app.db.base import Base


class ChannelAccount(Base):
    """메신저 채널(telegram) 연동. 사용자마다 자기 봇을 등록한다. 봇 소유자 1명만 대화할 수 있다 (pairing 으로 연결)."""

    __tablename__ = "channel_accounts"
    __table_args__ = (UniqueConstraint("user_id", "channel", name="uq_channel_accounts_user_channel"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    channel = Column(String(20), nullable=False, default="telegram")
    token_enc = Column(Text, nullable=False)  # 봇 토큰 (Fernet 암호화)
    bot_username = Column(String(100), nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    status = Column(String(20), nullable=False, default="pending")  # pending(미연결) | connected | error
    last_error = Column(String(500), nullable=True)
    # 연결된 Telegram 계정. 비어 있으면 아직 pairing 전이라 아무 메시지에도 응답하지 않는다 (/start <코드> 제외)
    external_user_id = Column(BigInteger, nullable=True)
    chat_id = Column(BigInteger, nullable=True)
    pair_code_hash = Column(String(64), nullable=True)
    pair_expires_at = Column(DateTime, nullable=True)
    conversation_id = Column(String(36), nullable=True)  # 이 채팅의 '현재 대화방'
    notify_schedules = Column(Boolean, nullable=False, default=True)  # 예약 작업 결과를 이 채팅으로 보낸다
    last_update_id = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, Text, UniqueConstraint

from app.db.base import Base


class ConnectorAccount(Base):
    """외부 서비스 계정 연결(OAuth). 지금은 Google 하나이고, 한 번 인증한 계정으로 여러 커넥터(Gmail·Calendar·Drive …)를 켠다.
    토큰은 Fernet 으로 암호화해 저장하고, 화면·AI 에는 계정 이메일과 켜진 커넥터 목록만 나간다."""

    __tablename__ = "connector_accounts"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_connector_accounts_user_provider"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String(20), nullable=False, default="google")
    email = Column(String(255), nullable=True)
    scopes = Column(Text, nullable=False, default="")  # 사용자가 허용한 OAuth 범위 (공백 구분)
    connectors = Column(JSON, nullable=False, default=list)  # 켜진 커넥터 id 목록 (gmail, google_calendar, ...)
    refresh_token_enc = Column(Text, nullable=True)
    access_token_enc = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # access token 만료 시각 (UTC, naive)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

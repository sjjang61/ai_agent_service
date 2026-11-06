import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Text

from app.db.base import Base


class ModelPrice(Base):
    """가격 페이지에서 갱신해 온 모델 단가 (USD / 1M 토큰). 코드의 기본 표보다 우선한다."""

    __tablename__ = "model_prices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model = Column(String(150), nullable=False, unique=True, index=True)
    input_price = Column(Float, nullable=False)
    cached_input_price = Column(Float, nullable=True)
    output_price = Column(Float, nullable=False)
    source_url = Column(String(1000), nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AppSetting(Base):
    """키-값 설정 (가격 정책 URL, 마지막 갱신 결과 등)."""

    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

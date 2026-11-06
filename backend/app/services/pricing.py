"""모델별 토큰 단가와 예상 비용 계산.

단가는 OpenAI 가격 페이지(https://developers.openai.com/api/docs/pricing)의 Standard 티어, 짧은 컨텍스트 기준이다
(2026-11-06 확인). USD / 1M 토큰. 가격은 자주 바뀌므로 표를 갱신하거나 MODEL_PRICES_JSON 으로 모델을 더하거나 덮어쓴다.

주의 (예상값이다):
- 사용량 기록에는 입력/출력 토큰만 있고 '캐시된 입력' 토큰은 구분하지 않는다. 그래서 입력은 모두 일반 입력 단가로 계산하며,
  프롬프트 캐시가 적용된 실제 청구액보다 높게(상한에 가깝게) 나올 수 있다.
- 이미지 모델은 이미지 출력 단가와 텍스트 입력 단가로 계산한다 (이미지 입력이 섞인 편집 요청은 입력이 더 비쌀 수 있다).
- 표에 없는 모델(다른 제공자·사내 모델 등)은 비용을 계산하지 않는다 (None).
"""
import json
import logging
import re
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# 모델: (입력, 캐시된 입력, 출력)  — USD / 1M tokens
PRICES: dict[str, tuple[float, Optional[float], float]] = {
    # 텍스트/채팅
    "gpt-6-astra": (10.00, 1.00, 50.00),
    "gpt-6.1-sol": (2.00, 0.10, 10.00),
    "gpt-6.1-terra": (1.00, 0.05, 5.00),
    "gpt-6-luna": (0.10, 0.01, 0.50),
    "gpt-6-sol": (2.00, 0.20, 10.00),
    "gpt-5.6-sol": (4.00, 0.40, 20.00),
    "gpt-5.6-terra": (2.00, 0.20, 12.00),
    "gpt-5.6-luna": (0.20, 0.02, 1.20),
    "gpt-5.5": (5.00, 0.50, 30.00),
    "gpt-5.5-pro": (30.00, None, 180.00),
    "gpt-5.4": (2.50, 0.25, 15.00),
    "gpt-5.4-pro": (30.00, None, 180.00),
    "gpt-5.4-mini": (0.75, 0.075, 4.50),
    "gpt-5.4-nano": (0.20, 0.02, 1.25),
    "gpt-5.2": (1.75, 0.175, 14.00),
    "gpt-5.2-pro": (21.00, None, 168.00),
    "gpt-5.1": (1.25, 0.125, 10.00),
    "gpt-5": (1.25, 0.125, 10.00),
    "gpt-5-mini": (0.25, 0.025, 2.00),
    "gpt-5-nano": (0.05, 0.005, 0.40),
    "gpt-5-pro": (15.00, None, 120.00),
    "gpt-4.1": (2.00, 0.50, 8.00),
    "gpt-4.1-mini": (0.40, 0.10, 1.60),
    "gpt-4o": (2.50, 1.25, 10.00),
    "gpt-4o-mini": (0.15, 0.075, 0.60),
    "o3": (2.00, 0.50, 8.00),
    "o3-pro": (20.00, None, 80.00),
    # 이미지 생성: (텍스트 입력, 텍스트 캐시 입력, 이미지 출력)
    "gpt-image-2": (5.00, 1.25, 30.00),
    "gpt-image-2.5-sunburst": (5.00, 1.25, 30.00),
    "gpt-image-2.5-flare": (5.00, 1.25, 30.00),
    "gpt-image-2.6-sunburst": (5.00, 1.25, 30.00),
    "gpt-image-2.6-flare": (5.00, 1.25, 30.00),
    "gpt-image-1.5": (5.00, 1.25, 32.00),
    "gpt-image-1-mini": (2.00, 0.20, 8.00),
    "chatgpt-image-latest": (5.00, 1.25, 32.00),
}

_DATE_SUFFIX = re.compile(r"-(\d{4}-\d{2}-\d{2}|\d{8}|\d{4})$")
_custom: Optional[dict] = None


def _overrides() -> dict:
    """MODEL_PRICES_JSON: {"모델": [입력, 캐시 입력(또는 null), 출력], ...} (USD/1M tokens). 형식이 틀린 항목은 무시한다."""
    global _custom
    if _custom is None:
        _custom = {}
        raw = (getattr(settings, "MODEL_PRICES_JSON", "") or "").strip()
        if raw:
            try:
                for name, v in json.loads(raw).items():
                    _custom[str(name).lower()] = (float(v[0]), None if v[1] is None else float(v[1]), float(v[2]))
            except Exception as e:  # noqa: BLE001
                logger.warning("[pricing] MODEL_PRICES_JSON 을 읽지 못했습니다: %s", e)
    return _custom


def get_price(model: str) -> Optional[tuple[float, Optional[float], float]]:
    """모델 이름으로 단가를 찾는다. 정확히 일치 → 날짜 접미사 제거 → 가장 긴 접두 일치(예: gpt-6-luna-2026-01-01)."""
    m = (model or "").strip().lower()
    if not m:
        return None
    table = {**PRICES, **_overrides()}
    if m in table:
        return table[m]
    base = _DATE_SUFFIX.sub("", m)
    if base in table:
        return table[base]
    best = max((k for k in table if m.startswith(k + "-")), key=len, default=None)
    return table[best] if best else None


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    """예상 비용(USD). 단가를 모르는 모델이면 None."""
    p = get_price(model)
    if p is None:
        return None
    return (max(0, input_tokens) * p[0] + max(0, output_tokens) * p[2]) / 1_000_000

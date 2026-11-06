import asyncio
from types import SimpleNamespace

import pytest

from app.services import pricing
from app.services.pricing import estimate_cost_usd, get_price


def test_known_models_cost():
    # gpt-6-luna: 입력 $0.10 / 출력 $0.50 (1M 토큰당)
    assert estimate_cost_usd("gpt-6-luna", 1_000_000, 1_000_000) == pytest.approx(0.60)
    assert estimate_cost_usd("gpt-5.6-luna", 500_000, 100_000) == pytest.approx(0.10 + 0.12)
    assert estimate_cost_usd("gpt-image-2", 1000, 4000) == pytest.approx(0.005 + 0.12)      # 텍스트 입력 + 이미지 출력
    assert estimate_cost_usd("gpt-6-luna", 0, 0) == 0


def test_model_name_matching():
    assert get_price("GPT-6-LUNA") == get_price("gpt-6-luna")
    assert get_price("gpt-6-luna-2026-01-15") == get_price("gpt-6-luna")        # 날짜 접미사
    assert get_price("gpt-5.4-mini-20260101") == get_price("gpt-5.4-mini")      # mini 가 gpt-5.4 로 잘못 붙지 않는다
    assert get_price("gpt-5.4-mini")[0] == 0.75 and get_price("gpt-5.4")[0] == 2.50
    assert get_price("claude-sonnet-5-5") is None and get_price("") is None
    assert estimate_cost_usd("some-internal-model", 100, 100) is None


def test_custom_prices_override(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(pricing, "_custom", None)
    monkeypatch.setattr(settings, "MODEL_PRICES_JSON", '{"my-model": [1, null, 2], "gpt-6-luna": [1, 0.1, 1], "bad": "x"}')
    assert estimate_cost_usd("my-model", 1_000_000, 1_000_000) == pytest.approx(3.0)
    assert estimate_cost_usd("gpt-6-luna", 1_000_000, 0) == pytest.approx(1.0)       # 기본 표를 덮어쓴다
    monkeypatch.setattr(pricing, "_custom", None)


def test_fold_costs_by_model_and_flags_unpriced():
    from app.services.token_usage_service import TokenUsageService

    rows = [
        SimpleNamespace(d="a", model_name="gpt-6-luna", input_tokens=1_000_000, output_tokens=0, request_count=2),
        SimpleNamespace(d="a", model_name="gpt-6-sol", input_tokens=1_000_000, output_tokens=0, request_count=1),
        SimpleNamespace(d="b", model_name="mystery", input_tokens=500, output_tokens=5, request_count=1),
        SimpleNamespace(d="b", model_name="gpt-6-luna", input_tokens=0, output_tokens=1_000_000, request_count=1),
    ]
    out = TokenUsageService._fold(rows, lambda r: r.d)
    assert out["a"]["cost"] == pytest.approx(0.10 + 2.00) and out["a"]["requests"] == 3 and not out["a"]["incomplete"]
    assert out["b"]["cost"] == pytest.approx(0.50) and out["b"]["incomplete"] is True       # 단가를 모르는 모델이 섞임
    row = TokenUsageService._row(out["a"])
    assert row["total_tokens"] == 2_000_000 and row["cost_usd"] == pytest.approx(2.10)

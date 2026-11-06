import asyncio
import html
import json

import pytest

from app.services import pricing, pricing_update as pu


def astro(props: dict) -> str:
    """Astro 직렬화([0,값]/[1,배열])로 island 태그를 만든다."""
    def enc(v):
        if isinstance(v, dict):
            return [0, {k: enc(x) for k, x in v.items()}]
        if isinstance(v, list):
            return [1, [enc(x) for x in v]]
        return [0, v]
    return f'<astro-island props="{html.escape(json.dumps(enc(props)), quote=True)}"></astro-island>'


PAGE = (
    astro({"tier": "standard", "rows": [
        ["gpt-9-new", 1, 0.1, 1.25, 5],                      # 최신 모델: 캐시 쓰기 열이 있는 5칸
        ["gpt-9-old (<272K context length)", 2, 0.5, 8],    # 이전 모델: 4칸, 괄호 설명 제거
        ["gpt-9-pro", 30, "-", 180],                          # 캐시 입력 단가 없음
    ]})
    + astro({"tier": "batch", "rows": [["gpt-9-new", 0.5, 0.05, 0.6, 2.5]]})              # Batch 는 무시
    + astro({"groups": [{"model": "realtime-x", "rows": [["Audio", 32, 64, 0.4]]}]})       # 이미지가 아닌 groups 는 건너뛴다
    + astro({"groups": [{"model": "gpt-image-9", "rows": [["Image", 8, 30, 2], ["Text", 5, "-", 1.25]]}]})
    + astro({"groups": [{"model": "gpt-image-9", "rows": [["Image", 4, 15, 1], ["Text", 2.5, "-", 0.625]]}]})   # 두 번째(Batch)는 무시
)

TABLE_PAGE = """<h2>Models</h2><table><tr><td></td><td>Caching</td></tr>
<tr><th>Model</th><th>Input</th><th>Output</th><th>Cached input</th></tr>
<tr><td>gpt-t1</td><td>$1.00</td><td>$4.00</td><td>$0.10</td></tr>
<tr><td>gpt-t2 (preview)</td><td>$2.50</td><td>$10.00</td><td>-</td></tr>
<tr><td>gpt-t3</td><td>$0.20</td><td>$1.00</td><td>$0.02</td></tr></table>
<table><tr><th>Model</th><th>Input</th><th>Output</th></tr><tr><td>gpt-t1</td><td>$9</td><td>$9</td></tr></table>"""


def test_parse_islands_picks_standard_text_and_first_image_island():
    got = pu.parse_islands(PAGE)
    assert got["gpt-9-new"] == (1.0, 0.1, 5.0) and got["gpt-9-old"] == (2.0, 0.5, 8.0)
    assert got["gpt-9-pro"] == (30.0, None, 180.0)
    assert got["gpt-image-9"] == (5.0, 1.25, 30.0)       # (텍스트 입력, 텍스트 캐시 입력, 이미지 출력) — 첫 번째 이미지 표만
    assert "realtime-x" not in got


def test_parse_tables_uses_first_occurrence_and_cleans_names():
    got = pu.parse_tables(TABLE_PAGE)
    assert got == {"gpt-t1": (1.0, 0.1, 4.0), "gpt-t2": (2.5, None, 10.0), "gpt-t3": (0.2, 0.02, 1.0)}


def test_parse_rejects_nonsense_and_requires_enough_models(monkeypatch):
    async def no_llm(page):
        return {}

    monkeypatch.setattr(pu, "parse_with_llm", no_llm)
    with pytest.raises(pu.PricingError):
        asyncio.run(pu.parse_pricing("<html>가격 없음</html>"))
    prices, method = asyncio.run(pu.parse_pricing(PAGE))
    assert method == "structured" and len(prices) >= 3
    prices, method = asyncio.run(pu.parse_pricing(TABLE_PAGE))
    assert method == "table"
    assert pu.parse_islands(astro({"tier": "standard", "rows": [["bad", -1, 0, 5], ["huge", 99999, 0, 5], ["n/a", "-", 0, 5]]})) == {}


def test_llm_fallback_used_when_no_structure(monkeypatch):
    async def fake_llm(page):
        return {"m1": (1.0, None, 2.0), "m2": (1.0, None, 2.0), "m3": (1.0, None, 2.0)}

    monkeypatch.setattr(pu, "parse_with_llm", fake_llm)
    prices, method = asyncio.run(pu.parse_pricing("<p>plain text</p>"))
    assert method == "llm" and set(prices) == {"m1", "m2", "m3"}


@pytest.mark.parametrize("url", [
    "http://example.com/pricing", "ftp://example.com", "https://", "javascript:alert(1)",
    "https://127.0.0.1/x", "https://localhost/x", "https://10.0.0.5/pricing", "https://169.254.169.254/latest/meta-data",
])
def test_url_validation_blocks_private_and_non_https(url):
    with pytest.raises(pu.PricingError):
        pu.validate_public_url(url)


def test_public_https_url_is_accepted(monkeypatch):
    import socket

    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
    assert pu.validate_public_url("https://example.com/pricing?x=1") == "https://example.com/pricing?x=1"
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.1.2.3", 443))])    # 이름이 사설 주소로 풀리면 거부
    with pytest.raises(pu.PricingError):
        pu.validate_public_url("https://sneaky.example.com/")


def test_db_prices_override_defaults_but_not_custom_json(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(pricing, "_custom", None)
    monkeypatch.setattr(settings, "MODEL_PRICES_JSON", "")
    pricing.set_db_prices({"gpt-6-luna": (9.0, None, 9.0), "brand-new": (1.0, None, 2.0)})
    assert pricing.estimate_cost_usd("gpt-6-luna", 1_000_000, 0) == pytest.approx(9.0)        # 갱신 단가가 기본 표보다 우선
    assert pricing.estimate_cost_usd("brand-new", 1_000_000, 1_000_000) == pytest.approx(3.0)
    monkeypatch.setattr(pricing, "_custom", None)
    monkeypatch.setattr(settings, "MODEL_PRICES_JSON", '{"gpt-6-luna": [1, null, 1]}')
    assert pricing.estimate_cost_usd("gpt-6-luna", 1_000_000, 0) == pytest.approx(1.0)        # MODEL_PRICES_JSON 이 가장 우선
    src = {p["model"]: p["source"] for p in pricing.effective_prices()}
    assert src["gpt-6-luna"] == "custom" and src["brand-new"] == "page" and src["gpt-4o"] == "default"
    monkeypatch.setattr(pricing, "_custom", None)
    pricing.set_db_prices({})

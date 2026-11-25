"""구매 수량 조합 비교: 같은 상품을 N개 사려 할 때 판매 구성(1개입, 2개입 묶음 …)과 판매처별 배송비를 반영해
총액이 가장 낮은 조합을 계산한다. 모델이 산수를 틀리지 않도록 계산만 맡는 순수 함수다 (사이트에 접속하지 않는다).

- 한 판매처의 한 구성만 몇 개 사는 조합을 본다 (구성을 섞어 담는 경우는 보지 않는다).
- 요청한 개수(N)와 정확히 맞는 조합이 '기본 답변', N보다 많이 사는 조합은 '초과 구매 제안'이다.
  초과 구매는 총액이 더 싸거나, 총액은 늘지만 1개당 가격이 더 싼 경우를 구분해 알려 준다.
"""
import json
import math
from typing import Any, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

DEFAULT_EXTRA_RATIO = 0.5  # 요청 개수의 최대 +50% 까지만 초과 구매를 제안한다
MAX_ROWS = 3


class Offer(BaseModel):
    seller: str = Field(description="판매처(또는 사이트) 이름")
    option: str = Field(default="", description="구성 이름 (예: '1개', '2개입 묶음', '5봉×4')")
    pack_units: int = Field(ge=1, description="이 구성 1건에 들어 있는 낱개 수 (예: 2개 묶음이면 2)")
    price: float = Field(gt=0, description="이 구성 1건의 가격(원). 할인·쿠폰 적용 전 표시가")
    shipping: float = Field(default=0, ge=0, description="이 판매처의 배송비(원). 무료배송이면 0")
    free_over: Optional[float] = Field(default=None, ge=0, description="상품 합계가 이 금액 이상이면 배송비 무료 (조건부 무료일 때만)")
    url: str = Field(default="", description="상품 주소 (선택)")


class ComboInput(BaseModel):
    target_units: int = Field(ge=1, le=1000, description="사용자가 사려는 낱개 수")
    offers: list[Offer] = Field(min_length=1, max_length=40, description="화면에서 확인한 판매 구성들")
    extra_ratio: float = Field(default=DEFAULT_EXTRA_RATIO, ge=0, le=2, description="초과 구매를 어디까지 볼지 (0.5 = 요청 개수의 150% 까지)")


def _ship(o: Offer, subtotal: float) -> float:
    if o.free_over is not None and subtotal >= o.free_over:
        return 0.0
    return float(o.shipping)


def _row(o: Offer, qty: int) -> dict:
    subtotal = o.price * qty
    ship = _ship(o, subtotal)
    units = o.pack_units * qty
    total = subtotal + ship
    return {
        "seller": o.seller, "option": o.option or f"{o.pack_units}개", "qty": qty, "units": units,
        "subtotal": round(subtotal), "shipping": round(ship), "total": round(total),
        "per_unit": round(total / units, 1), "url": o.url,
    }


def compute(target: int, offers: list[Offer], extra_ratio: float = DEFAULT_EXTRA_RATIO) -> dict:
    limit = target + math.floor(target * extra_ratio)
    exact, over = [], []
    for o in offers:
        q = 1
        while o.pack_units * q <= limit:
            units = o.pack_units * q
            if units == target:
                exact.append(_row(o, q))
            elif units > target:
                over.append(_row(o, q))
            q += 1
    exact.sort(key=lambda r: (r["total"], r["per_unit"]))
    over.sort(key=lambda r: (r["total"], r["per_unit"]))
    best = exact[0] if exact else None
    out: dict[str, Any] = {"target_units": target, "best_exact": best, "exact_ranking": exact[:MAX_ROWS]}
    if best is None:
        out["note"] = f"정확히 {target}개로 맞는 구성이 없습니다. 아래 초과 구매 조합을 참고하세요."
    cheaper_total, lower_unit_only = [], []
    for r in over:
        if best is None or r["total"] < best["total"]:
            cheaper_total.append(r)
        elif r["per_unit"] < best["per_unit"]:
            lower_unit_only.append(r)
    out["extra_cheaper_total"] = cheaper_total[:MAX_ROWS]  # 더 많이 사는데 총액이 더 싼 경우: 가장 강한 추천
    out["extra_lower_unit_price_only"] = sorted(lower_unit_only, key=lambda r: r["per_unit"])[:MAX_ROWS]  # 총액은 늘지만 개당은 싼 경우
    out["how_to_report"] = (
        "기본 답변은 best_exact(요청 개수 기준). extra_cheaper_total 이 있으면 '요청보다 N개 더 사도 총액이 ○원 더 싸다'고 한 줄로 제안하고, "
        "extra_lower_unit_price_only 는 '개당은 싸지만 총액은 ○원 더 든다'고 구분해 적는다. 추측으로 가격·구성을 더하지 말 것."
    )
    return out


class PriceComboTool(BaseTool):
    name: str = "price_combo"
    description: str = (
        "Compare purchase-quantity combinations for the SAME product. Give the number of units the user wants and the offers you actually saw "
        "(seller, option name, units per pack, pack price, shipping, free-shipping threshold). Returns the cheapest total for exactly that many units "
        "and cheaper-per-unit or cheaper-total alternatives when buying a few more. Use it instead of doing the arithmetic yourself. "
        "Only include offers of the same model/spec. It does not browse anything."
    )
    args_schema: type[BaseModel] = ComboInput

    def _run(self, target_units: int, offers: list, extra_ratio: float = DEFAULT_EXTRA_RATIO, **_) -> str:
        parsed = [o if isinstance(o, Offer) else Offer(**o) for o in offers]
        return json.dumps(compute(target_units, parsed, extra_ratio), ensure_ascii=False)

    async def _arun(self, *args, **kwargs) -> str:
        return self._run(*args, **kwargs)

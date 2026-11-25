from app.tools.price_combo import Offer, PriceComboTool, compute
import json


def O(seller, option, units, price, ship=0, free=None):
    return Offer(seller=seller, option=option, pack_units=units, price=price, shipping=ship, free_over=free)


def test_exact_best_picks_cheapest_total_including_shipping():
    offers = [O("A", "1개", 1, 1000, ship=3000), O("B", "2개입", 2, 1900, ship=0)]
    r = compute(6, offers)
    assert r["best_exact"]["seller"] == "B" and r["best_exact"]["qty"] == 3 and r["best_exact"]["total"] == 5700


def test_free_shipping_threshold_changes_ranking():
    offers = [O("A", "1개", 1, 1000, ship=3000, free=5000)]
    assert compute(4, offers)["best_exact"]["total"] == 7000  # 4000 + 3000
    assert compute(5, offers)["best_exact"]["total"] == 5000  # 기준 이상이라 무료


def test_extra_purchase_cheaper_total_is_suggested():
    offers = [O("A", "1개", 1, 1000, ship=3000, free=7000), O("A2", "8개", 8, 6900, ship=0)]
    r = compute(6, offers)  # 6개: 6000+3000=9000, 8개: 6900
    assert r["best_exact"]["total"] == 9000
    assert r["extra_cheaper_total"][0]["units"] == 8 and r["extra_cheaper_total"][0]["total"] == 6900


def test_lower_unit_price_only_when_total_is_higher():
    offers = [O("A", "1개", 1, 1000), O("B", "10개", 10, 8000)]
    r = compute(6, offers, extra_ratio=1.0)
    assert r["best_exact"]["total"] == 6000 and not r["extra_cheaper_total"]
    assert r["extra_lower_unit_price_only"][0]["units"] == 10 and r["extra_lower_unit_price_only"][0]["per_unit"] == 800


def test_no_exact_match_and_extra_limit():
    offers = [O("A", "4개입", 4, 3000)]
    r = compute(6, offers, extra_ratio=0.5)
    assert r["best_exact"] is None and "note" in r
    assert r["extra_cheaper_total"][0]["units"] == 8
    assert compute(6, [O("A", "20개입", 20, 5000)])["extra_cheaper_total"] == []  # 150% 를 넘는 구매는 제안하지 않는다


def test_tool_runs_with_dict_offers():
    out = json.loads(PriceComboTool()._run(target_units=2, offers=[{"seller": "A", "pack_units": 1, "price": 500}]))
    assert out["best_exact"]["total"] == 1000

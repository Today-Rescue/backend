"""세트(럭키박스) 구성 계산 (BX-02, BX-03)

팩당 개수를 품목마다 1~4개로 전수 비교해서 남는 재고가 가장 적은 구성을 고른다.
남는 수가 같으면 팩 수가 많은 쪽.
"""
from itertools import combinations, product

MAX_PER_PACK = 4
MAX_ITEMS = 4  # 한 세트에 넣는 품목 수 상한 (4^4 = 256가지)
BUNDLE_DISCOUNT = 0.4  # 추천가 = 단품 합계의 60%, 100원 단위 버림


def evaluate(stocks: dict[int, int], per_pack: dict[int, int]) -> dict:
    """구성 하나 평가 → {packs, leftover, leftover_by_item}"""
    packs = min(stocks[i] // per_pack[i] for i in per_pack)
    left = {i: stocks[i] - packs * per_pack[i] for i in per_pack}
    return {"packs": packs, "leftover": sum(left.values()), "leftover_by_item": left}


def best_composition(stocks: dict[int, int]) -> dict | None:
    """품목별 재고 → 남는 재고가 가장 적은 {per_pack, packs, leftover, ...}. 1팩도 못 만들면 None"""
    ids = sorted(stocks)
    best = None
    for counts in product(range(1, MAX_PER_PACK + 1), repeat=len(ids)):
        per_pack = dict(zip(ids, counts))
        r = evaluate(stocks, per_pack)
        if r["packs"] < 1:
            continue
        key = (r["leftover"], -r["packs"])
        if best is None or key < best[0]:
            best = (key, {"per_pack": per_pack, **r})
    return best[1] if best else None


def recommended_price(prices: dict[int, int], per_pack: dict[int, int]) -> tuple[int, int]:
    """(단품 판매가 합계, 추천 팩 가격)"""
    unit_total = sum(prices[i] * n for i, n in per_pack.items())
    return unit_total, int(unit_total * (1 - BUNDLE_DISCOUNT)) // 100 * 100


def candidate_sets(stocks: dict[int, int], limit: int = 3) -> list[dict]:
    """추천 조합 후보 (BX-01). 재고 많은 품목 상위 4개에서 2~3개 조합 → 많이 묶이는 순"""
    top = [i for i, q in sorted(stocks.items(), key=lambda x: -x[1]) if q > 0][:MAX_ITEMS]
    results = []
    for size in (2, 3):
        for ids in combinations(top, size):
            comp = best_composition({i: stocks[i] for i in ids})
            if comp:
                bundled = sum(comp["per_pack"][i] * comp["packs"] for i in ids)
                results.append((-bundled, comp["leftover"], comp))
    results.sort(key=lambda x: (x[0], x[1]))
    return [c for _, _, c in results[:limit]]

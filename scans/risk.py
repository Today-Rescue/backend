"""위험도 판단 규칙 (기획서 10장)

예상 잔여 = R − (M − R) / t경과 × t남은 × k
- R: 남은 수량 (스캔 수량), M: 오늘 만든 수량
- t경과: 오픈 ~ 촬영 시각, t남은: 촬영 시각 ~ 마감 (시간)
- k: 저녁 보정계수

| 단계 | 조건 (하나라도) |
| 위험 | 당일·하루 + 예상 잔여 5개 이상 / 당일·하루 + 예상 잔여가 남은 수량의 40% 이상 |
| 주의 | 당일·하루 + 예상 잔여 2~4개 / 최근 5영업일 중 3일 이상 남음 /
|      | 2일+ + 이월 재고(예상 잔여)가 내일 추천 생산량의 50% 초과 |
| 여유 | 그 외 |
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.utils import timezone

from items.models import Item
from records.models import DailyRecord

K = 0.6  # 저녁 보정계수
DANGER_LEFT = 5  # 예상 잔여 N개 이상이면 위험
DANGER_RATIO = 0.4  # 예상 잔여가 남은 수량의 N 이상이면 위험
CAUTION_LEFT = 2  # 예상 잔여 2~4개면 주의
REPEAT_WINDOW = 5  # 최근 N영업일
REPEAT_MIN = 3  # 중 N일 이상 남으면 주의
CARRYOVER_RATIO = 0.5  # 2일+ 이월 재고가 내일 추천량의 N 초과면 주의

DANGER = "danger"
CAUTION = "caution"
SAFE = "safe"
LEVEL_ORDER = {DANGER: 0, CAUTION: 1, SAFE: 2}

PERISHABLE = {Item.ShelfLife.TODAY, Item.ShelfLife.DAY1}
SHELF_LABEL = {
    Item.ShelfLife.TODAY: "오늘 소비기한",
    Item.ShelfLife.DAY1: "내일 품질 저하",
    Item.ShelfLife.DAY2: "2일 이상 보관",
}


@dataclass
class Risk:
    level: str
    expected_left: int
    reason: str


def hours_between(start: datetime, end: datetime) -> float:
    return max((end - start).total_seconds() / 3600, 0.0)


def store_hours(store, at: datetime) -> tuple[float, float] | None:
    """(t경과, t남은). 영업시간이 없으면 None"""
    if store.open_time is None or store.close_time is None:
        return None
    at = timezone.localtime(at).replace(tzinfo=None)
    opened = datetime.combine(at.date(), store.open_time)
    closes = datetime.combine(at.date(), store.close_time)
    return hours_between(opened, at), hours_between(at, closes)


def expected_left(left: int, made: int, elapsed_h: float, remaining_h: float, k: float = K) -> int:
    """마감 시점 예상 잔여. 판매 속도를 알 수 없으면 (만든 수량 없음, 오픈 직후) 남은 수량 그대로"""
    if left <= 0:
        return 0
    if elapsed_h <= 0 or made <= left:
        return left
    rate = (made - left) / elapsed_h
    return max(round(left - rate * remaining_h * k), 0)


def classify(shelf_life: str, left: int, expected: int, repeat_days: int,
             tomorrow_rec: int | None = None) -> Risk:
    """tomorrow_rec: 2일+ 품목의 내일 추천 생산량 (모르면 None → 이월 조건 건너뜀)"""
    if left <= 0:
        return Risk(SAFE, 0, "다 팔렸어요")
    perishable = shelf_life in PERISHABLE
    label = SHELF_LABEL.get(shelf_life, "")

    if perishable and (expected >= DANGER_LEFT or expected >= left * DANGER_RATIO) and expected > 0:
        return Risk(DANGER, expected, f"{label} · 마감 때 약 {expected}개 남을 것 같아요")
    if perishable and expected >= CAUTION_LEFT:
        return Risk(CAUTION, expected, f"{label} · 마감 때 약 {expected}개 남을 것 같아요")
    if (shelf_life == Item.ShelfLife.DAY2 and tomorrow_rec is not None and expected > 0
            and expected > tomorrow_rec * CARRYOVER_RATIO):
        return Risk(CAUTION, expected, f"이월 재고 약 {expected}개가 내일 추천량({tomorrow_rec}개)의 절반을 넘어요")
    if repeat_days >= REPEAT_MIN:
        return Risk(CAUTION, expected, f"최근 {REPEAT_WINDOW}영업일 중 {repeat_days}일 남았어요")
    if not perishable:
        return Risk(SAFE, expected, label)
    return Risk(SAFE, expected, "마감 전에 다 팔릴 것 같아요")


def repeat_left_days(store_id: int, before: date, item_ids: list[int]) -> dict[int, int]:
    """품목별 최근 N영업일(기록이 있는 날) 중 남은 날 수 (DB-04와 같은 데이터)"""
    rows = (
        DailyRecord.objects.filter(store_id=store_id, item_id__in=item_ids, date__lt=before,
                                   left_qty__isnull=False)
        .order_by("item_id", "-date")
        .values_list("item_id", "left_qty")
    )
    seen: dict[int, int] = {}
    result: dict[int, int] = {}
    for item_id, left in rows:
        if seen.get(item_id, 0) >= REPEAT_WINDOW:
            continue
        seen[item_id] = seen.get(item_id, 0) + 1
        if left > 0:
            result[item_id] = result.get(item_id, 0) + 1
    return result


def made_qty(store_id: int, target: date, item_ids: list[int]) -> dict[int, int]:
    """오늘 만든 수량 (최초 진열 + 추가 생산이 반영된 일일 기록)"""
    return dict(
        DailyRecord.objects.filter(store_id=store_id, date=target, item_id__in=item_ids)
        .values_list("item_id", "made_qty")
    )


def evaluate(store, at: datetime, items: list[Item], quantities: dict[int, int]) -> dict[int, Risk]:
    """품목별 위험도. quantities = {item_id: 남은 수량}"""
    ids = [it.id for it in items]
    target = timezone.localtime(at).date()
    made = made_qty(store.id, target, ids)
    repeat = repeat_left_days(store.id, target, ids)
    hours = store_hours(store, at)
    tomorrow = tomorrow_recommended(store, target, items)

    result = {}
    for it in items:
        left = quantities.get(it.id, 0)
        if hours:
            exp = expected_left(left, made.get(it.id, 0), *hours)
        else:
            exp = left  # 영업시간을 모르면 판매 속도 없이 남은 수량 그대로
        result[it.id] = classify(it.shelf_life, left, exp, repeat.get(it.id, 0), tomorrow.get(it.id))
    return result


def tomorrow_recommended(store, today: date, items: list[Item]) -> dict[int, int]:
    """2일+ 품목의 내일 추천 생산량 (#24). 2일+ 품목이 없으면 계산하지 않음"""
    if not any(it.shelf_life == Item.ShelfLife.DAY2 for it in items):
        return {}
    from dashboard.recommend import build_recommendation  # dashboard → scans.risk 순환 import 방지

    rec = build_recommendation(store, today + timedelta(days=1))
    return {r["item_id"]: r["recommended"] for r in rec["items"]}


def summarize(risks: dict[int, Risk], quantities: dict[int, int]) -> dict:
    """SR-03 위험·주의·여유별 품목 수와 수량"""
    summary = {lv: {"item_count": 0, "quantity": 0} for lv in LEVEL_ORDER}
    for item_id, r in risks.items():
        summary[r.level]["item_count"] += 1
        summary[r.level]["quantity"] += quantities.get(item_id, 0)
    return summary

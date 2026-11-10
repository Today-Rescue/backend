from datetime import date, timedelta

from django.db.models import Avg, QuerySet

from .models import DailyRecord


# ── B가 호출 (이름·모양 고정) ──────────────────────────
def update_left_qty(store_id: int, date: date, quantities: dict[int, int]) -> None:
    """{item_id: 남은 수량}. 기록이 없으면 made_qty=0으로 새로 만듦"""
    for item_id, left in quantities.items():
        DailyRecord.objects.update_or_create(
            item_id=item_id,
            date=date,
            defaults={"store_id": store_id, "left_qty": left},
            create_defaults={"store_id": store_id, "left_qty": left, "made_qty": 0},
        )


def get_records(store_id: int, start: date, end: date) -> QuerySet[DailyRecord]:
    """대시보드용 기간 조회 (start, end 포함)"""
    return DailyRecord.objects.filter(store_id=store_id, date__range=(start, end)).select_related("item")


# ── 홈에서 사용 ──────────────────────────────────────
def recent_weekday_avg(store_id: int, target: date, weeks: int = 4) -> dict[int, dict]:
    """최근 N주 같은 요일 품목별 평균 {item_id: {made_avg, left_avg}}"""
    days = [target - timedelta(weeks=i) for i in range(1, weeks + 1)]
    rows = (
        DailyRecord.objects.filter(store_id=store_id, date__in=days)
        .values("item_id")
        .annotate(made_avg=Avg("made_qty"), left_avg=Avg("left_qty"))
    )
    return {r["item_id"]: {"made_avg": r["made_avg"], "left_avg": r["left_avg"]} for r in rows}

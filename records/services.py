from datetime import date, timedelta

from django.db import transaction
from django.db.models import Avg, Count, F, Q, QuerySet, Sum
from django.db.models.functions import Greatest

from common.exceptions import AppError
from items.models import Item

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


def apply_sale(store_id: int, date: date, item_id: int, qty: int) -> None:
    """판매 수량만큼 확정된 남은 수량을 차감해요. 최소 수량은 0이에요."""
    if qty <= 0:
        raise AppError("INVALID_QTY", "판매 수량은 1개 이상이어야 해요")

    updated = DailyRecord.objects.filter(
        store_id=store_id, date=date, item_id=item_id, left_qty__isnull=False
    ).update(left_qty=Greatest(F("left_qty") - qty, 0))
    if not updated:
        raise AppError("LEFT_NOT_CONFIRMED", "남은 수량이 아직 확정되지 않았어요")


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


def weekly_made_totals(store_id: int, target: date, days: int = 7) -> list[dict]:
    """target 포함 최근 N일의 일별 총 생산량 [{date, made_total}] (기록 없는 날은 0)"""
    start = target - timedelta(days=days - 1)
    rows = (
        DailyRecord.objects.filter(store_id=store_id, date__range=(start, target))
        .values("date")
        .annotate(total=Sum("made_qty"))
    )
    totals = {r["date"]: r["total"] for r in rows}
    result = []
    for i in range(days):
        d = start + timedelta(days=i)
        result.append({"date": d.isoformat(), "made_total": totals.get(d, 0)})
    return result


# ── 일일 기록 API에서 사용 ───────────────────────────
def get_day_records(store_id: int, target: date) -> list[dict]:
    """그날의 품목별 기록. 기록이 없는 품목은 made_qty 0, left_qty·sold_qty는 null"""
    records = {r.item_id: r for r in DailyRecord.objects.filter(store_id=store_id, date=target)}
    items = (
        Item.objects.filter(store_id=store_id)
        .filter(Q(is_active=True) | Q(id__in=records.keys()))
        .order_by("id")
    )
    rows = []
    for item in items:
        rec = records.get(item.id)
        made = rec.made_qty if rec else 0
        left = rec.left_qty if rec else None
        rows.append(
            {
                "item_id": item.id,
                "name": item.name,
                "made_qty": made,
                "left_qty": left,
                "sold_qty": made - left if left is not None else None,
                "sold_out": rec.sold_out if rec else False,
            }
        )
    return rows


@transaction.atomic
def upsert_day_records(store_id: int, target: date, rows: list[dict]) -> None:
    """품목별로 있으면 수정, 없으면 생성. 하나라도 잘못되면 전부 저장하지 않아요."""
    ids = [r["item_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise AppError("DUPLICATE_ITEM", "같은 품목이 두 번 들어 있어요")

    valid_ids = set(Item.objects.filter(store_id=store_id, is_active=True).values_list("id", flat=True))
    invalid = sorted(set(ids) - valid_ids)
    if invalid:
        raise AppError("INVALID_ITEM", f"이 가게의 품목이 아니에요: {invalid}")

    existing = {
        r.item_id: r for r in DailyRecord.objects.filter(store_id=store_id, date=target, item_id__in=ids)
    }
    for r in rows:
        prev = existing.get(r["item_id"])
        left = r["left_qty"] if "left_qty" in r else (prev.left_qty if prev else None)
        if left is not None and left > r["made_qty"]:
            raise AppError("INVALID_QTY", "남은 수량은 만든 수량보다 클 수 없어요")

        defaults = {"store_id": store_id, "made_qty": r["made_qty"]}
        if "left_qty" in r:
            defaults["left_qty"] = r["left_qty"]
        if "sold_out" in r:
            defaults["sold_out"] = r["sold_out"]
        DailyRecord.objects.update_or_create(item_id=r["item_id"], date=target, defaults=defaults)


def month_range(value: str | None) -> tuple[date, date]:
    """'2026-11' → (2026-11-01, 2026-12-01). end는 포함하지 않아요."""
    try:
        year, month = (int(x) for x in value.split("-"))
        start = date(year, month, 1)
        end = date(year + month // 12, month % 12 + 1, 1)
    except (AttributeError, ValueError):
        raise AppError("INVALID_MONTH", "month는 2026-11 형식으로 보내 주세요")
    return start, end


def month_summary(store_id: int, start: date, end: date) -> list[dict]:
    """기록이 있는 날짜별 요약. 남은 수량이 비어 있는 품목이 있으면 is_confirmed=False"""
    rows = (
        DailyRecord.objects.filter(store_id=store_id, date__gte=start, date__lt=end)
        .values("date")
        .annotate(
            made_total=Sum("made_qty"),
            sold_total=Sum(F("made_qty") - F("left_qty"), filter=Q(left_qty__isnull=False)),
            sold_out_count=Count("id", filter=Q(sold_out=True)),
            unconfirmed_count=Count("id", filter=Q(left_qty__isnull=True)),
        )
        .order_by("date")
    )
    return [
        {
            "date": r["date"],
            "made_total": r["made_total"] or 0,
            "sold_total": r["sold_total"] or 0,
            "has_sold_out": r["sold_out_count"] > 0,
            "is_confirmed": r["unconfirmed_count"] == 0,
        }
        for r in rows
    ]

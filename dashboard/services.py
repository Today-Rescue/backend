"""주간 대시보드 (DB-01~05) — '얼마나 덜 버렸나'

- 폐기: records.CloseRecord.disposed_qty (마감 기록)
- 할인 판매: listings.SalesEvent (일괄 할인 캠페인)
- 남은 날: records.DailyRecord.left_qty > 0 (위험도 규칙의 반복 잔여와 같은 데이터)
"""
from datetime import date, datetime, timedelta

from django.db.models import Sum
from django.utils import timezone

from items.models import Item
from listings.models import CampaignItem, SaleCampaign, SalesEvent
from records.models import CloseRecord, DailyRecord
from scans import risk

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]
RECENT_DAYS = risk.REPEAT_WINDOW  # 최근 5영업일
FREQUENT_MIN = 2  # 자주 남는 빵: 최근 5영업일 중 N일 이상
FREQUENT_LIMIT = 5
REDUCE_MIN = 4  # 다음 주 제안: N일 이상 남은 빵은 생산 줄이기
LOW_SALE_RATE = 0.5  # 할인 판매율이 이보다 낮으면 할인율 올리기 제안


def week_start_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _rate(now: int, before: int) -> float | None:
    return round((now - before) / before, 2) if before else None


def daily_waste(store_id: int, start: date) -> dict[date, int]:
    rows = (
        CloseRecord.objects.filter(store_id=store_id, date__range=(start, start + timedelta(days=6)))
        .values("date")
        .annotate(total=Sum("disposed_qty"))
    )
    return {r["date"]: r["total"] or 0 for r in rows}


def waste_summary(this: dict[date, int], last: dict[date, int]) -> dict:
    """DB-01 이번 주 폐기, 지난주 대비 증감률, 줄인 개수"""
    now, before = sum(this.values()), sum(last.values())
    return {
        "this_week": now,
        "last_week": before,
        "change_rate": _rate(now, before),  # -0.29 = 29% 감소. 지난주 0이면 null
        "reduced": before - now,  # 음수면 늘어남
    }


def discount_summary(store_id: int, start: date) -> dict:
    """DB-02 할인으로 판매한 수, 마감 세일 판매율(판매 수 ÷ 할인 대상 수)"""
    end = start + timedelta(days=6)
    campaigns = SaleCampaign.objects.filter(store_id=store_id, type=SaleCampaign.Type.DISCOUNT,
                                            started_at__date__range=(start, end))
    target = CampaignItem.objects.filter(campaign__in=campaigns).aggregate(s=Sum("start_qty"))["s"] or 0
    sold = SalesEvent.objects.filter(campaign__in=campaigns).aggregate(s=Sum("quantity"))["s"] or 0
    return {
        "campaign_count": campaigns.count(),
        "target_qty": target,
        "sold_qty": sold,
        "sale_rate": round(sold / target, 2) if target else None,
    }


def daily_compare(start: date, this: dict[date, int], last: dict[date, int]) -> tuple[list[dict], str]:
    """DB-03 요일별 폐기 비교 + 한 줄 해석"""
    rows = []
    for i in range(7):
        d = start + timedelta(days=i)
        rows.append({
            "date": d.isoformat(),
            "weekday": WEEKDAYS[i],
            "this_week": this.get(d, 0),
            "last_week": last.get(d - timedelta(days=7), 0),
        })

    if not any(r["this_week"] or r["last_week"] for r in rows):
        return rows, "아직 마감 기록이 없어요"
    worst = max(range(7), key=lambda i: rows[i]["this_week"])
    w = rows[worst]
    if w["this_week"] == 0:
        return rows, "이번 주는 폐기가 없었어요"
    diff = w["this_week"] - w["last_week"]
    day = WEEKDAY_KO[worst]
    if diff > 0:
        return rows, f"{day}요일 폐기가 {w['this_week']}개로 가장 많고, 지난주보다 {diff}개 늘었어요"
    if diff < 0:
        return rows, f"{day}요일 폐기가 {w['this_week']}개로 가장 많지만, 지난주보다 {-diff}개 줄었어요"
    return rows, f"{day}요일 폐기가 {w['this_week']}개로 가장 많아요"


def recent_business_days(store_id: int, until: date) -> list[date]:
    """until 이하에서 남은 수량이 확정된 최근 5영업일 (오래된 날짜부터)"""
    days = (
        DailyRecord.objects.filter(store_id=store_id, date__lte=until, left_qty__isnull=False)
        .values_list("date", flat=True).distinct().order_by("-date")[:RECENT_DAYS]
    )
    return sorted(days)


def frequent_leftovers(store_id: int, until: date) -> list[dict]:
    """DB-04 자주 남는 빵: 최근 5영업일 중 남은 날(점 표시)과 앱이 취한 조치"""
    days = recent_business_days(store_id, until)
    if not days:
        return []
    left = {
        (r.item_id, r.date): r.left_qty
        for r in DailyRecord.objects.filter(store_id=store_id, date__in=days, left_qty__isnull=False)
    }
    actions: dict[tuple[int, date], set[str]] = {}
    for ci in CampaignItem.objects.filter(campaign__store_id=store_id).select_related("campaign"):
        d = timezone.localtime(ci.campaign.started_at).date()
        if d in days:
            actions.setdefault((ci.item_id, d), set()).add(ci.campaign.type)

    rows = []
    for item in Item.objects.filter(store_id=store_id, is_active=True):
        dots = [{"date": d.isoformat(), "left": (left.get((item.id, d)) or 0) > 0} for d in days]
        n = sum(x["left"] for x in dots)
        if n < FREQUENT_MIN:
            continue
        acted = [actions.get((item.id, d), set()) for d in days]
        rows.append({
            "item_id": item.id,
            "name": item.name,
            "image_url": item.image_url,
            "left_days": n,
            "total_days": len(days),
            "days": dots,
            "actions": {
                "discount_days": sum(SaleCampaign.Type.DISCOUNT in a for a in acted),
                "bundle_days": sum(SaleCampaign.Type.BUNDLE in a for a in acted),
            },
        })
    rows.sort(key=lambda x: -x["left_days"])
    return rows[:FREQUENT_LIMIT]


def alert_time(store, hours: int) -> str | None:
    if store.close_time is None:
        return None
    t = datetime.combine(date.today(), store.close_time) - timedelta(hours=hours)
    return t.strftime("%H:%M")


def next_week_suggestion(store, waste: dict, discount: dict, frequent: list[dict]) -> dict | None:
    """DB-05 데이터 기반 제안 1개. 바로 적용할 수 있으면 action에 요청을 담아줌"""
    for f in frequent:
        if f["left_days"] >= REDUCE_MIN:
            return {
                "type": "reduce_production",
                "message": f"{f['name']}이(가) 최근 {f['total_days']}영업일 중 {f['left_days']}일 남았어요. "
                           f"내일 생산 추천을 확인해 보세요",
                "item_id": f["item_id"],
                "action": None,
            }
    if discount["sale_rate"] is not None and discount["sale_rate"] < LOW_SALE_RATE:
        return {
            "type": "raise_discount",
            "message": f"마감 세일 판매율이 {round(discount['sale_rate'] * 100)}%예요. 다음 주엔 40% 할인으로 시작해 보세요",
            "item_id": None,
            "action": None,
        }
    if waste["this_week"] > 0 and store.alert_hours_before < 3 and store.close_time:
        at = alert_time(store, 3)
        return {
            "type": "earlier_alert",
            "message": f"마감 알림을 {at}로 앞당기면 세일을 더 일찍 시작할 수 있어요",
            "item_id": None,
            "action": {"method": "PATCH", "path": f"/api/v1/stores/{store.id}", "body": {"alert_hours_before": 3}},
        }
    if waste["reduced"] > 0:
        return {
            "type": "keep",
            "message": f"지난주보다 {waste['reduced']}개 덜 버렸어요. 지금처럼 이어가 보세요",
            "item_id": None,
            "action": None,
        }
    return None


def closed_until_date(store_id: int, start: date, end: date) -> date | None:
    """그 주에서 마감 기록이 있는 마지막 날. 없으면 None"""
    return (
        CloseRecord.objects.filter(store_id=store_id, date__range=(start, end))
        .order_by("-date").values_list("date", flat=True).first()
    )


def build_dashboard(store, week: date) -> dict:
    start = week_start_of(week)
    this = daily_waste(store.id, start)
    last = daily_waste(store.id, start - timedelta(days=7))
    # 진행 중인 주는 마감 기록이 있는 마지막 요일까지만, 지난주도 같은 요일까지 비교
    end = start + timedelta(days=6)
    closed_until = end if end < timezone.localdate() else closed_until_date(store.id, start, end)
    if closed_until is None:
        this_cmp, last_cmp = {}, {}
    else:
        this_cmp = {d: v for d, v in this.items() if d <= closed_until}
        last_cmp = {d: v for d, v in last.items() if d <= closed_until - timedelta(days=7)}
    waste = waste_summary(this_cmp, last_cmp)
    waste["compared_until"] = WEEKDAYS[closed_until.weekday()] if closed_until else None
    discount = discount_summary(store.id, start)
    daily, comment = daily_compare(start, this, last)
    until = min(start + timedelta(days=6), timezone.localdate())
    frequent = frequent_leftovers(store.id, until)
    return {
        "week_start": start.isoformat(),
        "week_end": (start + timedelta(days=6)).isoformat(),
        "waste": waste,
        "discount": discount,
        "daily_waste": daily,
        "daily_comment": comment,
        "frequent_leftovers": frequent,
        "suggestion": next_week_suggestion(store, waste, discount, frequent),
    }

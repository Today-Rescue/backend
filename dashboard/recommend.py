"""내일 생산 추천 (RE-01~05, 기획서 9.1)

같은 요일 평균 판매 → 날씨 보정(강수확률) → 공휴일 보정 → 마감 결과 보정
- 판매 기록이 3일보다 적으면 '오늘 판매 수(없으면 만든 수량)'로 시작
- 마감 결과: 오늘 완판 +, N일 연속 남음 −(평균 남은 수), 이월 재고 −
"""
import math
from datetime import date, timedelta

from django.db.models import Avg, F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import AppError
from items.models import Item
from records.models import CloseRecord, DailyRecord
from stores.models import Store
from weather.services import get_weather, is_holiday

WEEKS = 4  # 같은 요일 평균: 최근 N주
MIN_HISTORY_DAYS = 3  # 판매 기록이 이보다 적으면 오늘 기준으로 시작
RAIN_RULES = ((70, -0.15), (40, -0.08))  # (강수확률 이상, 손님 변화)
HOLIDAY_CHANGE = 0.20
SOLD_OUT_BOOST = 0.10
REPEAT_MIN = 3  # N일 연속 남으면 줄이기
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

SOURCES = {"weather": "기상청 단기예보", "holiday": "한국천문연구원 특일 정보"}


def rain_change(pop: int | None) -> float:
    if pop is None:
        return 0.0
    for threshold, change in RAIN_RULES:
        if pop >= threshold:
            return change
    return 0.0


def weekday_avg_sold(store_id: int, target: date) -> dict[int, float]:
    """최근 N주 같은 요일 품목별 평균 판매 (만든 − 남은)"""
    days = [target - timedelta(weeks=i) for i in range(1, WEEKS + 1)]
    rows = (
        DailyRecord.objects.filter(store_id=store_id, date__in=days, left_qty__isnull=False)
        .values("item_id")
        .annotate(avg=Avg(F("made_qty") - F("left_qty")))
    )
    return {r["item_id"]: r["avg"] for r in rows}


def history_days(store_id: int, before: date) -> int:
    return (
        DailyRecord.objects.filter(store_id=store_id, date__lt=before, left_qty__isnull=False)
        .values("date").distinct().count()
    )


def leftover_streak(store_id: int, item_id: int, until: date) -> tuple[int, float]:
    """until까지 연속으로 남은 날 수와 그 기간 평균 남은 수량"""
    rows = (
        DailyRecord.objects.filter(store_id=store_id, item_id=item_id, date__lte=until, left_qty__isnull=False)
        .order_by("-date").values_list("left_qty", flat=True)[:10]
    )
    streak = []
    for left in rows:
        if left <= 0:
            break
        streak.append(left)
    return len(streak), (sum(streak) / len(streak) if streak else 0.0)


def step_rows(rows: list[tuple[str, int]], weather_change: float, holiday_change: float) -> list[dict]:
    """RE-03 단계별 총량 + 이전 단계 대비 증감률

    날씨·공휴일은 적용한 보정률 그대로(예: -0.15), 마감 결과는 실제 총량 변화율. 첫 단계는 null
    """
    result = []
    for i, (label, total) in enumerate(rows):
        if i == 0:
            rate = None
        elif i == 1:
            rate = weather_change
        elif i == 2:
            rate = holiday_change
        else:
            prev = rows[i - 1][1]
            rate = round((total - prev) / prev, 2) if prev else None
        result.append({"label": label, "total": total, "change_rate": rate})
    return result


def last_business_day(store_id: int, target: date) -> date:
    """추천일 이전 마지막 영업일 (만든 수량 기록이 있는 날). 쉬는 날을 건너뛰어요. 없으면 전날"""
    last = (
        DailyRecord.objects.filter(store_id=store_id, date__lt=target, made_qty__gt=0)
        .order_by("-date").values_list("date", flat=True).first()
    )
    return last or target - timedelta(days=1)


def build_recommendation(store, target: date) -> dict:
    today = last_business_day(store.id, target)
    items = list(Item.objects.filter(store=store, is_active=True).order_by("id"))
    today_rec = {r.item_id: r for r in DailyRecord.objects.filter(store=store, date=today)}
    closes = {c.item_id: c for c in CloseRecord.objects.filter(store=store, date=today)}

    # 기준: 같은 요일 평균 판매 (기록이 부족하면 오늘 기준)
    enough = history_days(store.id, target) >= MIN_HISTORY_DAYS
    avg = weekday_avg_sold(store.id, target) if enough else {}

    # 조건 (RE-02)
    w = get_weather(store.nx, store.ny, target) if store.nx is not None and store.ny is not None else None
    pop = w.pop_max if w else None
    weather_change = rain_change(pop)
    holiday = is_holiday(target)
    holiday_change = HOLIDAY_CHANGE if holiday else 0.0

    rows = []
    steps = {"base": 0, "weather": 0, "holiday": 0, "closing": 0}
    for it in items:
        rec = today_rec.get(it.id)
        made_today = rec.made_qty if rec else 0
        if it.id in avg:
            base = avg[it.id]
        elif rec and rec.left_qty is not None:
            base = rec.made_qty - rec.left_qty  # 오늘 판매 수
        else:
            base = made_today

        tags = []
        after_weather = base * (1 + weather_change)
        if weather_change:
            tags.append("비 예보")
        after_holiday = after_weather * (1 + holiday_change)
        if holiday_change:
            tags.append("공휴일")

        qty = after_holiday
        if rec and rec.sold_out:
            qty = qty * (1 + SOLD_OUT_BOOST)
            tags.append("오늘 완판")
        carry = closes[it.id].carryover_qty if it.id in closes else 0
        if carry:  # 내일 팔 재고만큼 덜 만들기 (남은 빵을 이미 반영하므로 연속 남음 보정은 생략)
            qty -= carry
            tags.append("이월 재고")
        else:
            streak, streak_avg = leftover_streak(store.id, it.id, today)
            if streak >= REPEAT_MIN:
                qty -= streak_avg
                tags.append(f"{streak}일 연속 남음")

        final = max(math.ceil(qty) if "오늘 완판" in tags else round(qty), 0)
        steps["base"] += base
        steps["weather"] += after_weather
        steps["holiday"] += after_holiday
        steps["closing"] += final
        rows.append({
            "item_id": it.id,
            "name": it.name,
            "image_url": it.image_url,
            "today_made": made_today,
            "recommended": final,
            "change": final - made_today,
            "carryover_qty": carry,
            "tags": tags,
        })

    today_total = sum(r["today_made"] for r in rows)
    total = steps["closing"]
    applied = (["비 예보"] if weather_change else []) + (["공휴일"] if holiday else [])
    applied += ["마감 결과"] if any(set(r["tags"]) - {"비 예보", "공휴일"} for r in rows) else []
    basis = "같은 요일 평균" if enough else "오늘 판매"
    return {
        "date": target.isoformat(),
        "base_date": today.isoformat(),  # '오늘'로 비교한 마지막 영업일
        "is_closed_day": WEEKDAYS[target.weekday()] in (store.closed_days or []),
        # RE-01
        "total": total,
        "today_total": today_total,
        "change": total - today_total,
        "summary": f"{basis} 기준" + (f" · {', '.join(applied)} 반영" if applied else ""),
        # RE-02
        "conditions": {
            "pop": pop,
            "weather_change": weather_change,
            "is_holiday": holiday,
            "holiday_change": holiday_change,
            "sources": [SOURCES["weather"], SOURCES["holiday"]],
        },
        # RE-03
        "steps": step_rows([
            (basis, round(steps["base"])),
            ("날씨 보정", round(steps["weather"])),
            ("공휴일 보정", round(steps["holiday"])),
            ("마감 결과 보정", total),
        ], weather_change, holiday_change),
        # RE-04
        "items": rows,
    }


# ── API ─────────────────────────────────────────
class RecommendationView(APIView):
    """GET /stores/{id}/recommendations?date=2026-11-15  내일 생산 추천 (RE-01~05)

    date: 추천받을 날 (생략하면 내일). 그 전날의 마감 결과를 반영
    """

    def get(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        raw = request.query_params.get("date")
        try:
            target = date.fromisoformat(raw) if raw else timezone.localdate() + timedelta(days=1)
        except ValueError:
            raise AppError("INVALID_DATE", "date=YYYY-MM-DD 형식으로 보내 주세요")
        return Response(build_recommendation(store, target))

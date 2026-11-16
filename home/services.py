from datetime import date

from records.services import recent_weekday_avg, weekly_made_totals
from weather.services import get_weather, is_holiday

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def build_home(store, target: date) -> dict:
    """날씨 + 최근 평균 + 주간 생산량 + 오늘 영업 여부 합치기"""
    weather = None
    if store.nx is not None and store.ny is not None:
        w = get_weather(store.nx, store.ny, target)
        if w:
            weather = {"tmax": w.tmax, "tmin": w.tmin, "pop_max": w.pop_max, "has_rain": w.has_rain}

    return {
        "date": target.isoformat(),
        "is_open_today": WEEKDAYS[target.weekday()] not in (store.closed_days or []),
        "weather": weather,  # None → 프론트에서 "날씨 정보 없음"
        "is_holiday": is_holiday(target),
        "recent_avg": recent_weekday_avg(store.id, target),
        "weekly_made": weekly_made_totals(store.id, target),
    }
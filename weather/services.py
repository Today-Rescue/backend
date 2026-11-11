from collections import defaultdict
from datetime import date, datetime, timedelta

from django.utils import timezone

from . import clients
from .models import Holiday, WeatherDaily

# 단기예보 발표 시각 (발표 후 약 10분 뒤부터 조회 가능)
BASE_HOURS = [2, 5, 8, 11, 14, 17, 20, 23]
AVAILABLE_DELAY = timedelta(minutes=10)


# ── A가 호출 (이름·모양 고정) ──────────────────────────
def get_weather(nx: int, ny: int, date: date) -> WeatherDaily | None:
    """없으면 None. 홈에서 None이면 '날씨 정보 없음' 표시"""
    return WeatherDaily.objects.filter(nx=nx, ny=ny, date=date).first()


def is_holiday(date: date) -> bool:
    return Holiday.objects.filter(date=date, is_holiday=True).exists()


# ── 날씨 ──────────────────────────────────────────────
def latest_base(now: datetime | None = None) -> tuple[str, str]:
    """지금 조회 가능한 가장 최근 발표 (base_date, base_time)"""
    now = (now or timezone.localtime()) - AVAILABLE_DELAY
    hours = [h for h in BASE_HOURS if h <= now.hour]
    if hours:
        return now.strftime("%Y%m%d"), f"{hours[-1]:02d}00"
    prev = now - timedelta(days=1)
    return prev.strftime("%Y%m%d"), "2300"


def _to_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize_forecast(items: list[dict]) -> dict[date, dict]:
    """단기예보 항목 → 날짜별 {tmax, tmin, pop_max, has_rain}

    - tmax/tmin: TMX(일 최고)/TMN(일 최저). 발표 시각에 따라 없는 날은 None
    - pop_max: POP(강수확률) 최댓값
    - has_rain: PTY(강수형태)가 0이 아닌 시간이 하나라도 있으면 True
    """
    by_date = defaultdict(lambda: {"tmax": None, "tmin": None, "pop_max": None, "has_rain": False})
    for it in items:
        d = datetime.strptime(it["fcstDate"], "%Y%m%d").date()
        cat, val = it["category"], it["fcstValue"]
        day = by_date[d]
        if cat == "TMX":
            day["tmax"] = _to_float(val)
        elif cat == "TMN":
            day["tmin"] = _to_float(val)
        elif cat == "POP":
            pop = int(val)
            day["pop_max"] = pop if day["pop_max"] is None else max(day["pop_max"], pop)
        elif cat == "PTY" and val != "0":
            day["has_rain"] = True
    return dict(by_date)


def update_weather(nx: int, ny: int, base: tuple[str, str] | None = None) -> int:
    """(nx, ny) 단기예보 받아서 WeatherDaily 저장. 저장한 날짜 수 반환"""
    base_date, base_time = base or latest_base()
    items = clients.fetch_vilage_fcst(nx, ny, base_date, base_time)
    summary = summarize_forecast(items)

    for d, day in summary.items():
        values = {"pop_max": day["pop_max"], "has_rain": day["has_rain"],
                  "base_date": base_date, "base_time": base_time}
        # 늦은 발표분엔 오늘 TMX/TMN이 없을 수 있음 → 기존 값을 None으로 덮지 않음
        if day["tmax"] is not None:
            values["tmax"] = day["tmax"]
        if day["tmin"] is not None:
            values["tmin"] = day["tmin"]
        WeatherDaily.objects.update_or_create(nx=nx, ny=ny, date=d, defaults=values)
    return len(summary)


def store_grids() -> list[tuple[int, int]]:
    """가게들이 쓰는 (nx, ny) 목록 (중복 제거)"""
    from stores.models import Store

    return list(
        Store.objects.exclude(nx=None).exclude(ny=None)
        .values_list("nx", "ny").distinct()
    )


def update_all_weather() -> dict[tuple[int, int], int | str]:
    """모든 가게 격자 갱신. 격자별 결과 {(nx, ny): 저장 날짜 수 | 에러 메시지}"""
    base = latest_base()
    results = {}
    for nx, ny in store_grids():
        try:
            results[(nx, ny)] = update_weather(nx, ny, base)
        except Exception as e:  # 한 격자가 실패해도 나머지는 계속
            results[(nx, ny)] = str(e)
    return results


# ── 특일 ──────────────────────────────────────────────
def update_holidays(year: int, month: int) -> int:
    """해당 월 특일 저장. 저장한 건수 반환"""
    items = clients.fetch_holidays(year, month)
    for it in items:
        d = datetime.strptime(str(it["locdate"]), "%Y%m%d").date()
        Holiday.objects.update_or_create(
            date=d,
            defaults={"name": it["dateName"][:30], "is_holiday": it["isHoliday"] == "Y"},
        )
    return len(items)


def update_upcoming_holidays(months: int = 2) -> int:
    """이번 달부터 N개월 특일 저장"""
    today = timezone.localdate()
    year, month = today.year, today.month
    total = 0
    for _ in range(months):
        total += update_holidays(year, month)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return total

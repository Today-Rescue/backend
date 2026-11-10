from datetime import date

from .models import Holiday, WeatherDaily


# ── A가 호출 (이름·모양 고정) ──────────────────────────
def get_weather(nx: int, ny: int, date: date) -> WeatherDaily | None:
    """없으면 None. 홈에서 None이면 '날씨 정보 없음' 표시"""
    return WeatherDaily.objects.filter(nx=nx, ny=ny, date=date).first()


def is_holiday(date: date) -> bool:
    return Holiday.objects.filter(date=date, is_holiday=True).exists()


# ── 내부 ──────────────────────────────────────────────
def summarize_forecast(raw: dict) -> dict[date, dict]:
    """단기예보 응답 → 날짜별 {tmax, tmin, pop_max, has_rain}"""
    raise NotImplementedError  # TODO(B)


def update_weather(nx: int, ny: int) -> None:
    raise NotImplementedError  # TODO(B)


def update_holidays(year: int, month: int) -> None:
    raise NotImplementedError  # TODO(B)

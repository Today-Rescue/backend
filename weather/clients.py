import requests
from django.conf import settings

from common.exceptions import ExternalAPIError

VILAGE_FCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
HOLIDAY_URL = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"


def _get(url: str, params: dict) -> dict:
    try:
        res = requests.get(
            url,
            params={"serviceKey": settings.DATA_GO_KR_SERVICE_KEY, "dataType": "JSON", **params},
            timeout=10,
        )
        res.raise_for_status()
        return res.json()
    except (requests.RequestException, ValueError) as e:
        raise ExternalAPIError("DATA_GO_KR_ERROR", "공공데이터 응답이 없어요") from e


def fetch_vilage_fcst(nx: int, ny: int, base_date: str, base_time: str) -> dict:
    """기상청 단기예보"""
    return _get(VILAGE_FCST_URL, {
        "numOfRows": 1000, "pageNo": 1,
        "base_date": base_date, "base_time": base_time, "nx": nx, "ny": ny,
    })


def fetch_holidays(year: int, month: int) -> dict:
    """특일(공휴일) 정보"""
    return _get(HOLIDAY_URL, {"solYear": year, "solMonth": f"{month:02d}", "numOfRows": 50})

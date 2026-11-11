import requests
from django.conf import settings

from common.exceptions import ExternalAPIError

VILAGE_FCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
HOLIDAY_URL = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"


def _get(url: str, params: dict) -> dict:
    """공공데이터포털 호출 → body. 실패하면 ExternalAPIError(502)"""
    try:
        res = requests.get(
            url,
            params={"serviceKey": settings.DATA_GO_KR_SERVICE_KEY, **params},
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()
    except (requests.RequestException, ValueError) as e:
        raise ExternalAPIError("DATA_GO_KR_ERROR", "공공데이터 응답이 없어요") from e

    header = data.get("response", {}).get("header", {})
    if header.get("resultCode") != "00":
        raise ExternalAPIError("DATA_GO_KR_ERROR", f"공공데이터 오류: {header.get('resultMsg')}")
    return data["response"].get("body", {})


def _items(body: dict) -> list[dict]:
    """items가 비면 "", 1건이면 dict, 여러 건이면 list로 오는 걸 list로 통일"""
    items = body.get("items") or {}
    item = items.get("item", []) if isinstance(items, dict) else []
    return [item] if isinstance(item, dict) else list(item)


def fetch_vilage_fcst(nx: int, ny: int, base_date: str, base_time: str) -> list[dict]:
    """기상청 단기예보 → [{category, fcstDate, fcstTime, fcstValue, ...}]"""
    body = _get(VILAGE_FCST_URL, {
        "dataType": "JSON",
        "numOfRows": 1000,
        "pageNo": 1,
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
    })
    return _items(body)


def fetch_holidays(year: int, month: int) -> list[dict]:
    """특일(공휴일) → [{locdate, dateName, isHoliday, ...}]"""
    body = _get(HOLIDAY_URL, {
        "_type": "json",
        "solYear": year,
        "solMonth": f"{month:02d}",
        "numOfRows": 50,
    })
    return _items(body)

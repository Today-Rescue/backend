import requests
from django.conf import settings

from common.exceptions import ExternalAPIError

KAKAO_BASE = "https://dapi.kakao.com/v2/local"


def _get(path: str, params: dict) -> dict:
    try:
        res = requests.get(
            f"{KAKAO_BASE}{path}",
            params=params,
            headers={"Authorization": f"KakaoAK {settings.KAKAO_REST_API_KEY}"},
            timeout=5,
        )
        res.raise_for_status()
        return res.json()
    except requests.RequestException as e:
        raise ExternalAPIError("KAKAO_API_ERROR", "주소 정보를 가져오지 못했어요") from e


def coord_to_region(lat: float, lng: float) -> dict:
    """위경도 → {sido, sigungu, dong} (행정동 기준)"""
    data = _get("/geo/coord2regioncode.json", {"x": lng, "y": lat})
    for doc in data.get("documents", []):
        if doc.get("region_type") == "H":
            return {
                "sido": doc["region_1depth_name"],
                "sigungu": doc["region_2depth_name"],
                "dong": doc["region_3depth_name"],
            }
    return {}


def search_address(query: str) -> list[dict]:
    """주소 검색"""
    data = _get("/search/address.json", {"query": query})
    return data.get("documents", [])

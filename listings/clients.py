"""세트 이름 AI 생성 (Gemini). 실패하면 None → 기본 이름 사용"""
import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
NAME_MODEL = "gemini-3.1-flash-lite"  # 짧은 문구라 빠른 모델
TIMEOUT = 8

PROMPT = """빵집 마감 세일용 세트(럭키박스) 이름을 지어줘.
각 세트 구성을 보고 세트마다 이름 하나씩, 12자 이내 한국어로.
가볍고 먹음직스럽게, 이모지 없이.

{sets}
"""


def generate_names(sets: list[list[str]]) -> list[str] | None:
    """[[품목 구성 설명...], ...] → 세트 이름 목록 (같은 순서)"""
    lines = "\n".join(f"{i + 1}. " + ", ".join(s) for i, s in enumerate(sets))
    try:
        res = requests.post(
            GEMINI_URL.format(model=NAME_MODEL),
            headers={"x-goog-api-key": settings.GEMINI_API_KEY},
            json={
                "contents": [{"parts": [{"text": PROMPT.format(sets=lines)}]}],
                "generationConfig": {
                    "temperature": 0.8,
                    "responseMimeType": "application/json",
                    "responseSchema": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
            },
            timeout=TIMEOUT,
        )
        res.raise_for_status()
        names = json.loads(res.json()["candidates"][0]["content"]["parts"][0]["text"])
        if len(names) != len(sets):
            return None
        return [str(n).strip()[:50] for n in names]
    except (requests.RequestException, KeyError, IndexError, ValueError) as e:
        logger.warning("bundle name generation failed: %s", e)
        return None

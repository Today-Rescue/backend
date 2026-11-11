"""사진 인식 AI 호출 (Gemini)

다른 AI(Claude 등)로 바꾸려면 analyze_shelf()만 같은 모양으로 다시 구현하면 돼요.
"""
import base64
import json
import logging

import requests
from django.conf import settings

from common.exceptions import ExternalAPIError

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT = 30  # 초. 넘으면 다음 모델로

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "status": {"type": "STRING", "enum": ["ok", "too_dark", "no_items"]},
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "item_id": {"type": "INTEGER"},
                    "quantity": {"type": "INTEGER"},
                    "uncertain": {"type": "BOOLEAN"},
                },
                "required": ["item_id", "quantity", "uncertain"],
            },
        },
    },
    "required": ["status", "items"],
}


def _call(model: str, image_bytes: bytes, prompt: str) -> dict:
    res = requests.post(
        GEMINI_URL.format(model=model),
        headers={"x-goog-api-key": settings.GEMINI_API_KEY},
        json={
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg",
                                     "data": base64.b64encode(image_bytes).decode()}},
                    {"text": prompt},
                ],
            }],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": RESPONSE_SCHEMA,
            },
        },
        timeout=TIMEOUT,
    )
    res.raise_for_status()
    text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def analyze_shelf(image_bytes: bytes, prompt: str) -> tuple[dict, str]:
    """진열대 사진 → ({status, items:[{item_id, quantity, uncertain}]}, 사용한 모델)

    settings.GEMINI_MODELS 순서대로 시도하고, 모두 실패하면 ExternalAPIError(502)
    """
    last_error = None
    for model in settings.GEMINI_MODELS:
        try:
            return _call(model, image_bytes, prompt), model
        except (requests.RequestException, KeyError, IndexError, ValueError) as e:
            logger.warning("gemini %s failed: %s", model, e)
            last_error = e
    raise ExternalAPIError("SCAN_AI_ERROR", "사진을 분석하지 못했어요. 잠시 후 다시 시도해 주세요") from last_error

"""사진 인식 AI 호출 (Gemini)

다른 AI(Claude 등)로 바꾸려면 analyze_shelf()만 같은 모양으로 다시 구현하면 돼요.
"""
import base64
import json
import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
FALLBACK_RESERVE = 5  # 마지막 모델(빠른 모델)을 위해 남겨두는 시간(초)
MIN_ATTEMPT_SECONDS = 2  # 남은 시간이 이보다 적으면 시도하지 않음

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
                    "confidence": {"type": "NUMBER"},
                },
                "required": ["item_id", "quantity", "confidence"],
            },
        },
    },
    "required": ["status", "items"],
}


class AITimeout(Exception):
    """제한 시간 안에 어떤 모델도 응답하지 못함"""


def _call(model: str, image_bytes: bytes, prompt: str, timeout: float) -> dict:
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
        timeout=timeout,
    )
    res.raise_for_status()
    text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def analyze_shelf(image_bytes: bytes, prompt: str, deadline: float) -> tuple[dict, str]:
    """진열대 사진 → ({status, items:[{item_id, quantity, confidence}]}, 사용한 모델)

    settings.GEMINI_MODELS 순서대로 시도. deadline(time.monotonic 기준)까지 못 받으면 AITimeout
    """
    models = settings.GEMINI_MODELS
    for i, model in enumerate(models):
        remaining = deadline - time.monotonic()
        is_last = i == len(models) - 1
        timeout = remaining if is_last else remaining - FALLBACK_RESERVE
        if timeout < MIN_ATTEMPT_SECONDS:
            continue
        try:
            return _call(model, image_bytes, prompt, timeout=timeout), model
        except (requests.RequestException, KeyError, IndexError, ValueError) as e:
            logger.warning("gemini %s failed: %s", model, e)
    raise AITimeout()

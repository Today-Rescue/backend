from django.conf import settings

# TODO(B): Claude API 호출 (pip install anthropic 후 requirements.txt에 추가)


def analyze_shelf(image_bytes: bytes, media_type: str, prompt: str) -> dict:
    """진열대 사진 → LLM 원본 결과(dict)"""
    raise NotImplementedError

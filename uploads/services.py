import io
import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from common.exceptions import AppError

MAX_SIDE = 1600  # px. 긴 변 기준으로 줄임
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15MB
JPEG_QUALITY = 85


def resize_image(file) -> bytes:
    """업로드 파일 → 회전 보정 + 긴 변 MAX_SIDE로 줄인 JPEG bytes"""
    if file.size > MAX_UPLOAD_BYTES:
        raise AppError("IMAGE_TOO_LARGE", "15MB 이하 사진만 올릴 수 있어요")
    try:
        img = Image.open(file)
        img = ImageOps.exif_transpose(img)  # 휴대폰 사진 회전 정보 반영
        img = img.convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise AppError("INVALID_IMAGE", "사진 파일이 아니에요")

    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()


def save_bytes(data: bytes, folder: str = "uploads") -> str:
    """JPEG bytes 저장 → MEDIA 기준 URL 경로 (/media/uploads/2026/11/xxx.jpg)"""
    now = timezone.localtime()
    name = f"{folder}/{now:%Y/%m}/{uuid.uuid4().hex}.jpg"
    saved = default_storage.save(name, ContentFile(data))
    return default_storage.url(saved)


def save_image(file, folder: str = "uploads") -> str:
    """업로드 파일 → 줄여서 저장 → URL 경로"""
    return save_bytes(resize_image(file), folder)

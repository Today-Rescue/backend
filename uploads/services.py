import io
import re

from PIL import Image, ImageOps, UnidentifiedImageError

from common.exceptions import AppError

from .models import StoredImage

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


def image_path(image_id) -> str:
    return f"/api/v1/images/{image_id}.jpg"


def save_bytes(data: bytes, folder: str = "uploads") -> str:
    """JPEG bytes를 DB에 저장 → URL 경로 (/api/v1/images/{id}.jpg)

    Render 무료 서버는 재시작 때 서버 폴더가 비고, prod에선 /media/를 내려주지 않아서 DB에 저장해요
    """
    image = StoredImage.objects.create(folder=folder, data=data, size=len(data))
    return image_path(image.id)


def save_image(file, folder: str = "uploads") -> str:
    """업로드 파일 → 줄여서 저장 → URL 경로"""
    return save_bytes(resize_image(file), folder)


IMAGE_PATH_RE = re.compile(r"/api/v1/images/([0-9a-f-]{36})\.jpg")
REFERENCE_SIDE = 384  # px. AI 참고 사진은 작게


def load_image(url: str | None) -> bytes | None:
    """우리 서버 사진 주소(/api/v1/images/{id}.jpg, 전체 URL도 가능) → JPEG bytes. 외부 주소·없는 사진은 None"""
    m = IMAGE_PATH_RE.search(url or "")
    if not m:
        return None
    image = StoredImage.objects.filter(pk=m.group(1)).first()
    return bytes(image.data) if image else None


def thumbnail(data: bytes, side: int = REFERENCE_SIDE) -> bytes:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((side, side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()

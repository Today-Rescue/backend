import uuid

from django.db import models


class StoredImage(models.Model):
    """업로드 사진 원본 (스캔 사진, 품목 사진)

    Render 무료 서버는 재시작 때 서버 폴더 파일이 사라져서 DB에 저장해요.
    주소: /api/v1/images/{id}.jpg
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    folder = models.CharField(max_length=20)  # scans / uploads
    content_type = models.CharField(max_length=30, default="image/jpeg")
    data = models.BinaryField()
    size = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

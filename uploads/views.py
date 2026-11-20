from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import AppError

from .models import StoredImage
from .services import save_image


class UploadView(APIView):
    """POST /uploads  (multipart: file) → {url}"""

    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            raise AppError("FILE_REQUIRED", "사진을 선택해 주세요")
        path = save_image(file)
        return Response({"url": request.build_absolute_uri(path)}, status=201)


class ImageView(View):
    """GET /images/{id}.jpg  업로드한 사진 (스캔·품목)

    <img>가 바로 쓰는 주소라 DRF 대신 일반 Django view (Accept 협상 없음)
    """

    def get(self, request, pk):
        image = get_object_or_404(StoredImage, pk=pk)
        response = HttpResponse(bytes(image.data), content_type=image.content_type)
        response["Cache-Control"] = "public, max-age=31536000, immutable"  # 같은 id는 내용이 안 바뀜
        return response

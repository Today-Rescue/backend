from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import AppError

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

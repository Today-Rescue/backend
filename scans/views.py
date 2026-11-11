from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import AppError
from common.responses import ok
from stores.models import Store

from . import services
from .models import ShelfScan
from .serializers import ConfirmSerializer


class ScanCreateView(APIView):
    """POST /stores/{id}/scans  (multipart: image)

    응답 status
    - ok: items에 가게 전체 품목별 수량 (못 찾은 품목은 0, found=false)
    - too_dark / no_items: items 빈 배열 → 다시 찍기 안내
    """

    parser_classes = [MultiPartParser]

    def post(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        image = request.FILES.get("image")
        if not image:
            raise AppError("FILE_REQUIRED", "사진을 선택해 주세요")
        scan = services.create_scan(store, image)
        return Response({
            "scan_id": scan.id,
            "status": scan.status,
            "image_url": request.build_absolute_uri(scan.image_url),
            "items": services.scan_items(scan),
        }, status=201)


class ScanConfirmView(APIView):
    """POST /scans/{id}/confirm  body: {date, items:[{item_id, quantity}]}"""

    def post(self, request, pk):
        scan = get_object_or_404(ShelfScan, pk=pk)
        s = ConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.confirm_scan(scan, s.validated_data["date"], s.validated_data["items"])
        return ok()

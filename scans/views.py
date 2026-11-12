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


def _absolute(request, data: dict) -> dict:
    data["image_url"] = request.build_absolute_uri(data["image_url"])
    return data


class ScanCreateView(APIView):
    """POST /stores/{id}/scans  (multipart: image)

    status
    - ok: 모든 품목 인식 / partial: 일부만 인식 (found_count / total_count)
    - failed: 찾은 품목 없음 / timeout: 20초 초과·통신 실패 / too_dark: 사진 어두움
    어떤 status든 scan_id로 직접 입력 후 확정할 수 있음
    """

    parser_classes = [MultiPartParser]

    def post(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        image = request.FILES.get("image")
        if not image:
            raise AppError("FILE_REQUIRED", "사진을 선택해 주세요")
        scan = services.create_scan(store, image)
        return Response(_absolute(request, services.scan_response(scan)), status=201)


class ScanDetailView(APIView):
    """GET /scans/{id}  스캔 결과 다시 보기"""

    def get(self, request, pk):
        scan = get_object_or_404(ShelfScan, pk=pk)
        return Response(_absolute(request, services.scan_response(scan)))


class ScanConfirmView(APIView):
    """POST /scans/{id}/confirm  body: {date, items:[{item_id, quantity}]}"""

    def post(self, request, pk):
        scan = get_object_or_404(ShelfScan, pk=pk)
        s = ConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.confirm_scan(scan, s.validated_data["date"], s.validated_data["items"])
        return ok()

from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import AppError
from common.responses import ok
from stores.models import Store

from . import services
from .models import ShelfScan
from .serializers import ConfirmSerializer, RiskPreviewSerializer


def _absolute(request, data: dict) -> dict:
    data["image_url"] = request.build_absolute_uri(data["image_url"])
    return data


class ScanPurposeView(APIView):
    """GET /stores/{id}/scans/purpose  촬영 목적 추천 (CP-01 '지금 추천')

    마감 알림 시각 전이면 open(최초 진열), 이후면 close(재고 기록)
    """

    def get(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        return Response({"recommended": services.recommended_purpose(store)})


class ScanCreateView(APIView):
    """POST /stores/{id}/scans  (multipart: image, purpose?)

    purpose: open(최초 진열 → 오늘 만든 수량) / close(재고 기록 → 남은 수량). 안 보내면 시각 기준 추천값

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
        purpose = request.data.get("purpose") or None
        if purpose and purpose not in ShelfScan.Purpose.values:
            raise AppError("INVALID_PURPOSE", "purpose는 open 또는 close로 보내 주세요")
        scan = services.create_scan(store, image, purpose)
        return Response(_absolute(request, services.scan_response(scan)), status=201)


class ScanDetailView(APIView):
    """GET /scans/{id}  스캔 결과 다시 보기"""

    def get(self, request, pk):
        scan = get_object_or_404(ShelfScan, pk=pk)
        return Response(_absolute(request, services.scan_response(scan)))


class ScanRiskView(APIView):
    """POST /scans/{id}/risk  body: {items:[{item_id, quantity}]}

    확정 전에 수정한 수량으로 총 재고·위험도를 다시 계산 (SR-02·03). 저장하지 않음
    """

    def post(self, request, pk):
        scan = get_object_or_404(ShelfScan, pk=pk)
        s = RiskPreviewSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        quantities = {r["item_id"]: r["quantity"] for r in s.validated_data["items"]}
        return Response(_absolute(request, services.scan_response(scan, quantities)))


class ScanConfirmView(APIView):
    """POST /scans/{id}/confirm  body: {date, purpose?, items:[{item_id, quantity}]}

    purpose를 보내면 촬영 때 목적 대신 이 값으로 확정 (open → 만든 수량, close → 남은 수량)
    """

    def post(self, request, pk):
        scan = get_object_or_404(ShelfScan, pk=pk)
        s = ConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        services.confirm_scan(scan, d["date"], d["items"], d.get("purpose"))
        return ok()

from datetime import date

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import AppError
from stores.models import Store

from . import services
from .models import SaleCampaign
from .serializers import (
    BundleCalculateSerializer,
    BundleCreateSerializer,
    BundleRecommendSerializer,
    CampaignStatusSerializer,
    DiscountCreateSerializer,
    DiscountUpdateSerializer,
    SalesCreateSerializer,
)


class StoreCampaignView(APIView):
    """GET /stores/{id}/campaigns?date=&status=   세일 목록 (기본: 오늘)
    POST /stores/{id}/campaigns/discount           일괄 할인 시작 → StoreDiscountView
    """

    def get(self, request, store_id):
        get_object_or_404(Store, pk=store_id)
        try:
            target = date.fromisoformat(request.query_params.get("date") or timezone.localdate().isoformat())
        except ValueError:
            raise AppError("INVALID_DATE", "날짜는 2026-11-12 형식으로 보내 주세요")
        qs = SaleCampaign.objects.filter(store_id=store_id, started_at__date=target).order_by("-started_at")
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        return Response([services.campaign_response(c) for c in qs])


class StoreDiscountView(APIView):
    """GET /stores/{id}/campaigns/discount?discount_rate=30  할인 화면 품목 체크리스트 (SL-02)
    POST /stores/{id}/campaigns/discount  body: {discount_rate?, item_ids?, ends_at?}

    - item_ids 생략: 원터치 할인 (MN-05), 마지막 재고 스캔의 위험·주의 품목
    - discount_rate 생략: 30, ends_at 생략: 오늘 마감 시각
    """

    def get(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        try:
            rate = int(request.query_params.get("discount_rate", 30))
        except ValueError:
            rate = 0
        if rate not in services.DISCOUNT_RATES:
            raise AppError("INVALID_RATE", "할인율은 20, 30, 40, 50 중 하나예요")
        return Response(services.discount_options(store, rate))

    def post(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        s = DiscountCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        campaign = services.start_discount(store, d["discount_rate"], d.get("item_ids"), d.get("ends_at"))
        return Response(services.campaign_response(campaign), status=201)


class CampaignDetailView(APIView):
    """GET /campaigns/{id}   PATCH /campaigns/{id}  body: {discount_rate?, item_ids?}"""

    def get(self, request, pk):
        return Response(services.campaign_response(get_object_or_404(SaleCampaign, pk=pk)))

    def patch(self, request, pk):
        campaign = get_object_or_404(SaleCampaign, pk=pk)
        s = DiscountUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.update_discount(campaign, s.validated_data.get("discount_rate"), s.validated_data.get("item_ids"))
        return Response(services.campaign_response(campaign))


class CampaignStatusView(APIView):
    """PATCH /campaigns/{id}/status  body: {status: stopped | ended}"""

    def patch(self, request, pk):
        campaign = get_object_or_404(SaleCampaign, pk=pk)
        s = CampaignStatusSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.stop_campaign(campaign, s.validated_data["status"])
        return Response(services.campaign_response(campaign))


class BundleRecommendView(APIView):
    """POST /stores/{id}/bundles/recommend  body: {item_ids?}  → 추천 세트 최대 3개 (BX-01)"""

    def post(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        s = BundleRecommendSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(services.recommend_bundles(store, s.validated_data.get("item_ids")))


class BundleCalculateView(APIView):
    """POST /stores/{id}/bundles/calculate  body: {items:[{item_id, per_pack, qty?}]}  (BX-02, BX-03)"""

    def post(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        s = BundleCalculateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(services.calculate_bundle(store, s.validated_data["items"]))


class StoreBundleView(APIView):
    """POST /stores/{id}/campaigns/bundle  body: {name, price, items:[{item_id, per_pack, qty?}], ends_at?}"""

    def post(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        s = BundleCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        campaign = services.start_bundle(store, d["name"], d["price"], d["items"], d.get("ends_at"))
        return Response(services.campaign_response(campaign), status=201)


class CampaignSalesView(APIView):
    """GET /campaigns/{id}/sales   판매 내역 (최근 순)
    POST /campaigns/{id}/sales  판매 확정 → 남은 수량 차감
      일괄 할인: {channel: daangn|store, items:[{item_id, quantity}]}
      세트: {channel, packs}
    """

    def get(self, request, pk):
        campaign = get_object_or_404(SaleCampaign, pk=pk)
        events = campaign.sales.select_related("item", "campaign__bundle").order_by("-sold_at", "-id")
        return Response([services.sale_response(e) for e in events])

    def post(self, request, pk):
        campaign = get_object_or_404(SaleCampaign, pk=pk)
        s = SalesCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        events = services.record_sales(campaign, d["channel"], d.get("items"), d.get("packs"))
        return Response([services.sale_response(e) for e in events], status=201)


class StoreLiveView(APIView):
    """GET /stores/{id}/campaigns/live  마감 세일 현황 (LV-01~04)

    - discount: 진행률, 채널별 판매 수, 품목별 세일 전 → 현재 수량, 느린 품목과 할인율 올리기 제안
    - bundle: 판매 팩 / 전체 팩
    오늘 세일이 없으면 각각 null
    """

    def get(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        return Response(services.live_status(store))

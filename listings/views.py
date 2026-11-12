from datetime import date

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import AppError
from stores.models import Store

from . import services
from .models import SaleCampaign
from .serializers import CampaignStatusSerializer, DiscountCreateSerializer, DiscountUpdateSerializer


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
    """POST /stores/{id}/campaigns/discount  body: {discount_rate, item_ids, ends_at?}"""

    def post(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        s = DiscountCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        campaign = services.start_discount(
            store, s.validated_data["discount_rate"], s.validated_data["item_ids"], s.validated_data.get("ends_at")
        )
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

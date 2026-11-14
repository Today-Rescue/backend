from datetime import date

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import AppError
from stores.models import Store

from .services import build_dashboard


class DashboardView(APIView):
    """GET /stores/{id}/dashboard?week=2026-11-09

    week: 그 주의 아무 날짜 (월요일로 맞춤). 생략하면 이번 주
    """

    def get(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        try:
            week = date.fromisoformat(request.query_params.get("week") or timezone.localdate().isoformat())
        except ValueError:
            raise AppError("INVALID_WEEK", "week=YYYY-MM-DD 형식으로 보내 주세요")
        return Response(build_dashboard(store, week))

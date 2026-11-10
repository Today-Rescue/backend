from datetime import date

from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import AppError

from .services import build_dashboard


class DashboardView(APIView):
    """GET /stores/{id}/dashboard?week=2026-11-09"""

    def get(self, request, store_id):
        try:
            week = date.fromisoformat(request.query_params["week"])
        except (KeyError, ValueError):
            raise AppError("INVALID_WEEK", "week=YYYY-MM-DD 형식으로 보내 주세요")
        return Response(build_dashboard(store_id, week))

from datetime import date as date_cls

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import AppError
from stores.models import Store

from . import services
from .serializers import CalendarDaySerializer, RecordSerializer, RecordUpsertItemSerializer


def _ensure_store(store_id: int) -> None:
    if not Store.objects.filter(pk=store_id).exists():
        raise AppError("STORE_NOT_FOUND", "가게를 찾을 수 없어요", 404)


def _parse_date(value: str | None) -> date_cls:
    try:
        return date_cls.fromisoformat(value)
    except (TypeError, ValueError):
        raise AppError("INVALID_DATE", "날짜는 2026-11-10 형식으로 보내 주세요")


class RecordListView(APIView):
    """GET /stores/{id}/records?date="""

    @extend_schema(
        parameters=[OpenApiParameter("date", str, description="YYYY-MM-DD", required=True)],
        responses=RecordSerializer(many=True),
    )
    def get(self, request, store_id):
        _ensure_store(store_id)
        target = _parse_date(request.query_params.get("date"))
        return Response(RecordSerializer(services.get_day_records(store_id, target), many=True).data)


class RecordUpsertView(APIView):
    """PUT /stores/{id}/records/{date}  body: [{item_id, made_qty, left_qty, sold_out}]"""

    @extend_schema(request=RecordUpsertItemSerializer(many=True), responses=RecordSerializer(many=True))
    def put(self, request, store_id, date):
        _ensure_store(store_id)
        serializer = RecordUpsertItemSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        services.upsert_day_records(store_id, date, serializer.validated_data)
        return Response(RecordSerializer(services.get_day_records(store_id, date), many=True).data)


class CalendarView(APIView):
    """GET /stores/{id}/records/calendar?month=2026-11"""

    @extend_schema(
        parameters=[OpenApiParameter("month", str, description="YYYY-MM", required=True)],
        responses=CalendarDaySerializer(many=True),
    )
    def get(self, request, store_id):
        _ensure_store(store_id)
        start, end = services.month_range(request.query_params.get("month"))
        return Response(CalendarDaySerializer(services.month_summary(store_id, start, end), many=True).data)
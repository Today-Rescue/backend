"""판매 기록 조회: GET /stores/{store_id}/sales-records?date=

정가 판매 = 만든 − 남은 − 할인 판매 (남은 수량이 아직 없으면 null)
할인 판매 = 그날 마감 세일(SalesEvent) 수량 합
          (세트는 팩 수 × 팩당 개수를 품목별로 풀어서 더해요)
"""
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import AppError
from listings.models import SalesEvent
from stores.models import Store

from .models import CloseRecord
from .services import get_day_records


class SalesRecordItemSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    name = serializers.CharField()
    made = serializers.IntegerField()
    left = serializers.IntegerField(allow_null=True)
    regular_sold = serializers.IntegerField(allow_null=True)
    discount_sold = serializers.IntegerField()
    carryover = serializers.IntegerField(allow_null=True)
    disposed = serializers.IntegerField(allow_null=True)
    sold_out = serializers.BooleanField()


class SalesRecordTotalSerializer(serializers.Serializer):
    made = serializers.IntegerField()
    regular_sold = serializers.IntegerField()
    discount_sold = serializers.IntegerField()
    carryover = serializers.IntegerField()
    disposed = serializers.IntegerField()


class SalesRecordSerializer(serializers.Serializer):
    date = serializers.DateField()
    is_confirmed = serializers.BooleanField()
    is_closed = serializers.BooleanField()
    total = SalesRecordTotalSerializer()
    items = SalesRecordItemSerializer(many=True)


def _parse_date(value):
    if value is None:
        return timezone.localdate()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise AppError("INVALID_DATE", "date는 2026-11-14 형식으로 보내 주세요")


def _check_store(store_id):
    if not Store.objects.filter(pk=store_id).exists():
        raise AppError("STORE_NOT_FOUND", "가게를 찾을 수 없어요", status=404)


def _discount_sold(store_id, target):
    """{item_id: 그날 할인 판매 수량}"""
    start = timezone.make_aware(datetime.combine(target, time.min))
    end = start + timedelta(days=1)
    events = SalesEvent.objects.filter(
        campaign__store_id=store_id, sold_at__gte=start, sold_at__lt=end
    )

    sold = defaultdict(int)
    for row in events.filter(item__isnull=False).values("item_id").annotate(qty=Sum("quantity")):
        sold[row["item_id"]] += row["qty"]

    # 세트 판매: 팩 수 × 팩당 개수를 품목별로 풀어요
    for event in events.filter(item__isnull=True).select_related("campaign"):
        bundle = getattr(event.campaign, "bundle", None)
        if bundle is None:
            continue
        for bundle_item in bundle.items.all():
            sold[bundle_item.item_id] += bundle_item.per_pack * event.quantity
    return sold


def build_sales_record(store_id, target):
    day_rows = get_day_records(store_id, target)
    discount = _discount_sold(store_id, target)
    closes = {c.item_id: c for c in CloseRecord.objects.filter(store_id=store_id, date=target)}

    items = []
    for r in day_rows:
        made, left = r["made_qty"], r["left_qty"]
        discount_sold = discount.get(r["item_id"], 0)
        regular_sold = max(made - left - discount_sold, 0) if left is not None else None
        close = closes.get(r["item_id"])
        items.append(
            {
                "item_id": r["item_id"],
                "name": r["name"],
                "made": made,
                "left": left,
                "regular_sold": regular_sold,
                "discount_sold": discount_sold,
                "carryover": close.carryover_qty if close else None,
                "disposed": close.disposed_qty if close else None,
                "sold_out": r["sold_out"],
            }
        )

    made_items = [i for i in items if i["made"] > 0]
    return {
        "date": target.isoformat(),
        "is_confirmed": bool(made_items) and all(i["left"] is not None for i in made_items),
        "is_closed": bool(closes),
        "total": {
            "made": sum(i["made"] for i in items),
            "regular_sold": sum(i["regular_sold"] or 0 for i in items),
            "discount_sold": sum(i["discount_sold"] for i in items),
            "carryover": sum(i["carryover"] or 0 for i in items),
            "disposed": sum(i["disposed"] or 0 for i in items),
        },
        "items": items,
    }


class SalesRecordView(APIView):
    """GET /stores/{store_id}/sales-records?date=2026-11-14 (date를 안 보내면 오늘)"""

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "date", str, required=False, description="조회할 날짜 (2026-11-14 형식). 안 보내면 오늘"
            )
        ],
        responses=SalesRecordSerializer,
    )
    def get(self, request, store_id):
        _check_store(store_id)
        target = _parse_date(request.query_params.get("date"))
        return Response(build_sales_record(store_id, target))
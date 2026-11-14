from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import AppError
from items.models import Item

from .models import CloseRecord, DailyRecord
from .production import _check_store


# ── 요청·응답 모양 ───────────────────────────────
class ClosingRowSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    disposed_qty = serializers.IntegerField(min_value=0)  # 폐기
    carryover_qty = serializers.IntegerField(min_value=0)  # 내일 판매


class ClosingSerializer(serializers.Serializer):
    items = ClosingRowSerializer(many=True, allow_empty=False)


class ClosingItemSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    name = serializers.CharField()
    left_qty = serializers.IntegerField()
    disposed_qty = serializers.IntegerField()
    carryover_qty = serializers.IntegerField()
    sold_out = serializers.BooleanField()


class ClosingResultSerializer(serializers.Serializer):
    date = serializers.DateField()
    is_closed = serializers.BooleanField()
    items = ClosingItemSerializer(many=True)
    disposed_total = serializers.IntegerField()
    carryover_total = serializers.IntegerField()


# ── 로직 ─────────────────────────────────────────
def get_closing(store_id: int, target) -> dict:
    """그날 마감 기록. 마감 전이면 is_closed=False, items는 빈 배열"""
    _check_store(store_id)
    closes = list(
        CloseRecord.objects.filter(store_id=store_id, date=target)
        .select_related("item")
        .order_by("item_id")
    )
    sold_out = dict(
        DailyRecord.objects.filter(store_id=store_id, date=target).values_list("item_id", "sold_out")
    )
    items = [
        {
            "item_id": c.item_id,
            "name": c.item.name,
            "left_qty": c.left_qty,
            "disposed_qty": c.disposed_qty,
            "carryover_qty": c.carryover_qty,
            "sold_out": sold_out.get(c.item_id, False),
        }
        for c in closes
    ]
    return {
        "date": target,
        "is_closed": bool(items),
        "items": items,
        "disposed_total": sum(i["disposed_qty"] for i in items),
        "carryover_total": sum(i["carryover_qty"] for i in items),
    }


@transaction.atomic
def save_closing(store_id: int, target, rows: list[dict]) -> dict:
    """남은 빵을 폐기/내일 판매로 나눠 저장. 하나라도 잘못되면 전부 저장하지 않아요."""
    _check_store(store_id)

    ids = [r["item_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise AppError("DUPLICATE_ITEM", "같은 품목이 두 번 들어 있어요")

    valid = set(
        Item.objects.filter(store_id=store_id, is_active=True, id__in=ids).values_list("id", flat=True)
    )
    invalid = sorted(set(ids) - valid)
    if invalid:
        raise AppError("INVALID_ITEM", f"이 가게의 품목이 아니에요: {invalid}")

    records = {
        r.item_id: r
        for r in DailyRecord.objects.filter(store_id=store_id, date=target, item_id__in=ids)
    }
    for r in rows:
        rec = records.get(r["item_id"])
        if rec is None or rec.left_qty is None:
            raise AppError("LEFT_NOT_CONFIRMED", "남은 수량이 아직 확정되지 않았어요")
        if r["disposed_qty"] + r["carryover_qty"] != rec.left_qty:
            raise AppError("INVALID_QTY", "폐기와 내일 판매의 합이 남은 수량과 달라요")

        CloseRecord.objects.update_or_create(
            item_id=r["item_id"],
            date=target,
            defaults={
                "store_id": store_id,
                "left_qty": rec.left_qty,
                "disposed_qty": r["disposed_qty"],
                "carryover_qty": r["carryover_qty"],
                "closed_at": timezone.now(),
            },
        )
        if rec.left_qty == 0 and not rec.sold_out:  # 다 팔렸으면 완판
            rec.sold_out = True
            rec.save(update_fields=["sold_out"])

    return get_closing(store_id, target)


# ── API ─────────────────────────────────────────
class ClosingView(APIView):
    @extend_schema(summary="마감 기록 조회", responses=ClosingResultSerializer)
    def get(self, request, store_id, date):
        return Response(get_closing(store_id, date))

    @extend_schema(
        summary="마감 기록 저장 (폐기/내일 판매)",
        request=ClosingSerializer,
        responses=ClosingResultSerializer,
    )
    def put(self, request, store_id, date):
        s = ClosingSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        rows = [dict(i) for i in s.validated_data["items"]]
        return Response(save_closing(store_id, date, rows))
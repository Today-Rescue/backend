from datetime import date as date_cls

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import AppError
from items.models import Item
from stores.models import Store

from .models import DailyProduction, DailyRecord


# ── 요청 모양 ─────────────────────────────────────
class ProductionRowSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    qty = serializers.IntegerField()


class ProductionCreateSerializer(serializers.Serializer):
    date = serializers.DateField(required=False)  # 없으면 오늘
    source = serializers.ChoiceField(choices=DailyProduction.Source.values)  # initial / extra / edit
    items = ProductionRowSerializer(many=True, allow_empty=False)


# ── 로직 ─────────────────────────────────────────
def _check_store(store_id: int) -> None:
    if not Store.objects.filter(id=store_id).exists():
        raise AppError("STORE_NOT_FOUND", "가게를 찾을 수 없어요", 404)


def _parse_date(value: str | None) -> date_cls:
    if not value:
        return timezone.localdate()
    try:
        return date_cls.fromisoformat(value)
    except ValueError:
        raise AppError("INVALID_DATE", "date는 2026-11-14 형식으로 보내 주세요")


@transaction.atomic
def add_productions(store_id: int, target: date_cls, source: str, rows: list[dict]) -> list[dict]:
    """만든 수량 기록을 쌓고, 그날 품목별 총 만든 수량(made_qty)을 갱신해요.
    - initial(최초 진열): 이미 있던 최초 기록을 새 값으로 바꿔요
    - extra(추가 생산): 기존 수량에 더해요 (1개 이상)
    - edit(직접 수정): 기존 수량에 더하거나 빼요 (음수 가능)
    하나라도 잘못되면 전부 저장하지 않아요."""
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

    S = DailyProduction.Source
    for r in rows:
        if source == S.INITIAL and r["qty"] < 0:
            raise AppError("INVALID_QTY", "수량은 0 이상이어야 해요")
        if source == S.EXTRA and r["qty"] <= 0:
            raise AppError("INVALID_QTY", "추가 생산은 1개 이상이어야 해요")

    names = dict(Item.objects.filter(id__in=ids).values_list("id", "name"))
    result = []
    for r in rows:
        item_id, qty = r["item_id"], r["qty"]
        logs = DailyProduction.objects.filter(store_id=store_id, item_id=item_id, date=target)
        rec = DailyRecord.objects.filter(item_id=item_id, date=target).first()

        if source == S.INITIAL:
            logs.filter(source=S.INITIAL).delete()
            others = logs.exclude(source=S.INITIAL).aggregate(s=Sum("qty"))["s"] or 0
            made = qty + others
        else:
            made = (rec.made_qty if rec else 0) + qty

        if made < 0:
            raise AppError("INVALID_QTY", "만든 수량이 0보다 작아질 수 없어요")
        if rec and rec.left_qty is not None and rec.left_qty > made:
            raise AppError("INVALID_QTY", "남은 수량보다 적게 만들었다고 할 수 없어요")

        DailyProduction.objects.create(
            store_id=store_id, item_id=item_id, date=target, qty=qty, source=source
        )
        DailyRecord.objects.update_or_create(
            item_id=item_id, date=target, defaults={"store_id": store_id, "made_qty": made}
        )
        result.append({"item_id": item_id, "name": names[item_id], "qty": qty, "made_qty": made})
    return result


def get_productions(store_id: int, target: date_cls) -> dict:
    """그날 품목별 총 만든 수량과 기록(최초 진열·추가 생산 시각)"""
    _check_store(store_id)
    records = DailyRecord.objects.filter(store_id=store_id, date=target).select_related("item").order_by("item_id")
    logs = (
        DailyProduction.objects.filter(store_id=store_id, date=target)
        .select_related("item")
        .order_by("recorded_at", "id")
    )
    items = [{"item_id": r.item_id, "name": r.item.name, "made_qty": r.made_qty} for r in records]
    return {
        "date": target,
        "made_total": sum(i["made_qty"] for i in items),
        "items": items,
        "logs": [
            {
                "item_id": g.item_id,
                "name": g.item.name,
                "source": g.source,
                "qty": g.qty,
                "recorded_at": timezone.localtime(g.recorded_at),
            }
            for g in logs
        ],
    }


# ── API ─────────────────────────────────────────
class ProductionView(APIView):
    @extend_schema(
        summary="오늘 만든 수량 조회",
        parameters=[OpenApiParameter("date", str, description="YYYY-MM-DD, 없으면 오늘")],
    )
    def get(self, request, store_id):
        target = _parse_date(request.query_params.get("date"))
        return Response(get_productions(store_id, target))

    @extend_schema(summary="만든 수량 기록 (최초 진열·추가 생산·직접 수정)", request=ProductionCreateSerializer)
    def post(self, request, store_id):
        s = ProductionCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        target = d.get("date") or timezone.localdate()
        rows = add_productions(store_id, target, d["source"], [dict(i) for i in d["items"]])
        return Response({"date": target, "source": d["source"], "items": rows}, status=status.HTTP_201_CREATED)
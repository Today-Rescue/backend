from rest_framework import serializers


class RecordUpsertItemSerializer(serializers.Serializer):
    """PUT 요청 한 줄. 보내지 않은 left_qty, sold_out은 기존 값을 유지해요."""

    item_id = serializers.IntegerField()
    made_qty = serializers.IntegerField(min_value=0)
    left_qty = serializers.IntegerField(min_value=0, allow_null=True, required=False)
    sold_out = serializers.BooleanField(required=False)


class RecordSerializer(serializers.Serializer):
    """품목별 일일 기록 응답. left_qty가 null이면 미확정이라 sold_qty도 null"""

    item_id = serializers.IntegerField()
    name = serializers.CharField()
    made_qty = serializers.IntegerField()
    left_qty = serializers.IntegerField(allow_null=True)
    sold_qty = serializers.IntegerField(allow_null=True)
    sold_out = serializers.BooleanField()


class CalendarDaySerializer(serializers.Serializer):
    """달력 날짜별 요약. is_confirmed가 false면 남은 수량이 비어 있는 품목이 있다는 뜻"""

    date = serializers.DateField()
    made_total = serializers.IntegerField()
    sold_total = serializers.IntegerField()
    has_sold_out = serializers.BooleanField()
    is_confirmed = serializers.BooleanField()
from rest_framework import serializers

from .models import Store
from .services import latlng_to_grid

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class StoreSerializer(serializers.ModelSerializer):
    """POST /stores 요청: {name, lat, lng} → nx, ny는 서버에서 계산
    PATCH /stores/{id}: 동, 영업시간, 쉬는 요일, 마감 알림 같은 정보를 일부만 수정"""

    lat = serializers.FloatField(min_value=33.0, max_value=39.0)
    lng = serializers.FloatField(min_value=124.0, max_value=132.0)
    dong = serializers.CharField(max_length=30, required=False, allow_blank=True)
    open_time = serializers.TimeField(format="%H:%M", input_formats=["%H:%M"], required=False, allow_null=True)
    close_time = serializers.TimeField(format="%H:%M", input_formats=["%H:%M"], required=False, allow_null=True)
    closed_days = serializers.ListField(child=serializers.ChoiceField(choices=WEEKDAYS), required=False)

    class Meta:
        model = Store
        fields = [
            "id",
            "name",
            "lat",
            "lng",
            "nx",
            "ny",
            "dong",
            "open_time",
            "close_time",
            "closed_days",
            "alert_hours_before",
            "is_demo",
            "created_at",
        ]
        read_only_fields = ["nx", "ny", "is_demo", "created_at"]

    def validate_closed_days(self, value):
        """중복을 없애고 월~일 순서로 정렬해요"""
        return sorted(set(value), key=WEEKDAYS.index)

    def validate(self, attrs):
        lat = attrs.get("lat", getattr(self.instance, "lat", None))
        lng = attrs.get("lng", getattr(self.instance, "lng", None))
        if lat is not None and lng is not None:
            attrs["nx"], attrs["ny"] = latlng_to_grid(lat, lng)
        return attrs
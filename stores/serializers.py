from rest_framework import serializers

from .models import Store
from .services import latlng_to_grid


class StoreSerializer(serializers.ModelSerializer):
    """POST /stores 요청: {name, lat, lng} → nx, ny는 서버에서 계산"""

    lat = serializers.FloatField(min_value=33.0, max_value=39.0)
    lng = serializers.FloatField(min_value=124.0, max_value=132.0)

    class Meta:
        model = Store
        fields = ["id", "name", "lat", "lng", "nx", "ny", "is_demo", "created_at"]
        read_only_fields = ["nx", "ny", "is_demo", "created_at"]

    def validate(self, attrs):
        lat = attrs.get("lat", getattr(self.instance, "lat", None))
        lng = attrs.get("lng", getattr(self.instance, "lng", None))
        if lat is not None and lng is not None:
            attrs["nx"], attrs["ny"] = latlng_to_grid(lat, lng)
        return attrs

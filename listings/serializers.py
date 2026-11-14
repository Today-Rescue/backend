from rest_framework import serializers

from .services import DISCOUNT_RATES


class DiscountCreateSerializer(serializers.Serializer):
    discount_rate = serializers.ChoiceField(choices=DISCOUNT_RATES, default=30)
    # 없거나 비면 원터치 할인: 마지막 재고 스캔의 위험·주의 품목 (MN-05)
    item_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)


class DiscountUpdateSerializer(serializers.Serializer):
    discount_rate = serializers.ChoiceField(choices=DISCOUNT_RATES, required=False)
    item_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False, required=False)


class BundleRecommendSerializer(serializers.Serializer):
    item_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)


class BundleItemSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    per_pack = serializers.IntegerField(min_value=1)
    qty = serializers.IntegerField(min_value=0, required=False)  # 없으면 서버가 지금 남은 수량 사용


class BundleCalculateSerializer(serializers.Serializer):
    items = BundleItemSerializer(many=True, allow_empty=False)


class BundleCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=50)
    price = serializers.IntegerField(min_value=0)
    items = BundleItemSerializer(many=True, allow_empty=False)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)


class CampaignStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["stopped", "ended"])

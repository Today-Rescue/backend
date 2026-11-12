from rest_framework import serializers

from .services import DISCOUNT_RATES


class DiscountCreateSerializer(serializers.Serializer):
    discount_rate = serializers.ChoiceField(choices=DISCOUNT_RATES, default=30)
    item_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)


class DiscountUpdateSerializer(serializers.Serializer):
    discount_rate = serializers.ChoiceField(choices=DISCOUNT_RATES, required=False)
    item_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False, required=False)


class CampaignStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["stopped", "ended"])

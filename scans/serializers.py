from rest_framework import serializers

from .models import ShelfScan


class ConfirmItemSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=0)


class ConfirmSerializer(serializers.Serializer):
    date = serializers.DateField()
    purpose = serializers.ChoiceField(choices=ShelfScan.Purpose.choices, required=False)
    items = ConfirmItemSerializer(many=True, allow_empty=False)

from rest_framework import serializers


class ConfirmItemSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=0)


class ConfirmSerializer(serializers.Serializer):
    date = serializers.DateField()
    items = ConfirmItemSerializer(many=True, allow_empty=False)

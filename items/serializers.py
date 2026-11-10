from rest_framework import serializers

from .models import Item


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ["id", "store_id", "name", "price", "cost", "image_url", "is_active"]
        read_only_fields = ["store_id"]

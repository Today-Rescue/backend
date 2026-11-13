from rest_framework import serializers

from .models import Item


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ["id", "store_id", "name", "price", "cost", "image_url", "shelf_life", "is_active"]
        read_only_fields = ["store_id"]
        extra_kwargs = {"shelf_life": {"required": True}}
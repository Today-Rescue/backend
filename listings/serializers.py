from rest_framework import serializers

from .models import Listing, ListingItem


class ListingItemSerializer(serializers.ModelSerializer):
    item_id = serializers.IntegerField()
    name = serializers.CharField(source="item.name", read_only=True)

    class Meta:
        model = ListingItem
        fields = ["item_id", "name", "qty"]


class ListingSerializer(serializers.ModelSerializer):
    items = ListingItemSerializer(many=True)

    class Meta:
        model = Listing
        fields = [
            "id", "store_id", "type", "partner_name", "partner_contact",
            "pickup_date", "pickup_start", "pickup_end", "bundle_price",
            "status", "memo", "items", "created_at",
        ]
        read_only_fields = ["store_id", "status", "created_at"]

    # TODO(B): create() 에서 items 중첩 저장


class ListingStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Listing.Status.choices)

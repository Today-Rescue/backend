from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets

from stores.models import Store

from .models import Item
from .serializers import ItemSerializer


class StoreItemViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """GET·POST /stores/{store_id}/items"""

    serializer_class = ItemSerializer

    def get_queryset(self):
        return Item.objects.filter(store_id=self.kwargs["store_id"], is_active=True)

    def perform_create(self, serializer):
        store = get_object_or_404(Store, pk=self.kwargs["store_id"])
        serializer.save(store=store)


class ItemViewSet(mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """PATCH·DELETE /items/{id}"""

    queryset = Item.objects.all()
    serializer_class = ItemSerializer

    def perform_destroy(self, instance):
        # 기록·판매에서 참조하므로 실제 삭제 대신 숨김
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])

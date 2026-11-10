from django.urls import path

from . import views

store_items = views.StoreItemViewSet.as_view({"get": "list", "post": "create"})
item_detail = views.ItemViewSet.as_view({"patch": "partial_update", "delete": "destroy"})

urlpatterns = [
    path("stores/<int:store_id>/items", store_items),
    path("items/<int:pk>", item_detail),
]

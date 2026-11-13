from rest_framework import generics

from .models import Store
from .serializers import StoreSerializer


class StoreCreateView(generics.CreateAPIView):
    """POST /stores  body: {name, lat, lng}"""

    queryset = Store.objects.all()
    serializer_class = StoreSerializer


class StoreDetailView(generics.RetrieveUpdateAPIView):
    """GET /stores/{id}, PATCH /stores/{id} (일부 수정만 허용)"""

    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    http_method_names = ["get", "patch", "head", "options"]

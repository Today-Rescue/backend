from rest_framework import generics

from .models import Store
from .serializers import StoreSerializer


class StoreCreateView(generics.CreateAPIView):
    """POST /stores  body: {name, lat, lng}"""

    queryset = Store.objects.all()
    serializer_class = StoreSerializer


class StoreDetailView(generics.RetrieveAPIView):
    """GET /stores/{id}"""

    queryset = Store.objects.all()
    serializer_class = StoreSerializer

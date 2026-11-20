from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from stores.models import Store

from .schemas import HomeSerializer
from .services import build_home


class HomeView(APIView):
    """GET /stores/{id}/home"""

    @extend_schema(responses=HomeSerializer)
    def get(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        return Response(build_home(store, timezone.localdate()))
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from stores.models import Store

from .services import build_home


class HomeView(APIView):
    """GET /stores/{id}/home"""

    def get(self, request, store_id):
        store = get_object_or_404(Store, pk=store_id)
        return Response(build_home(store, timezone.localdate()))

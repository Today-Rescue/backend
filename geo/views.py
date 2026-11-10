from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import AppError

from . import clients


class RegionView(APIView):
    """GET /geo/region?lat=&lng="""

    def get(self, request):
        try:
            lat = float(request.query_params["lat"])
            lng = float(request.query_params["lng"])
        except (KeyError, ValueError):
            raise AppError("INVALID_COORD", "위경도를 확인해 주세요")
        return Response(clients.coord_to_region(lat, lng))


class SearchView(APIView):
    """GET /geo/search?q="""

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if not q:
            raise AppError("INVALID_QUERY", "검색어를 입력해 주세요")
        return Response(clients.search_address(q))

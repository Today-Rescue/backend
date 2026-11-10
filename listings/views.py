from common.responses import not_implemented
from rest_framework.views import APIView


class StoreListingView(APIView):
    """GET·POST /stores/{id}/listings"""

    def get(self, request, store_id):
        return not_implemented()

    def post(self, request, store_id):
        return not_implemented()


class ListingDetailView(APIView):
    """GET /listings/{id}"""

    def get(self, request, pk):
        return not_implemented()


class ListingStatusView(APIView):
    """PATCH /listings/{id}/status  body: {status}"""

    def patch(self, request, pk):
        return not_implemented()

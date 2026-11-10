from common.responses import not_implemented
from rest_framework.views import APIView


class ScanCreateView(APIView):
    """POST /stores/{id}/scans  (multipart: image)"""

    def post(self, request, store_id):
        return not_implemented()


class ScanConfirmView(APIView):
    """POST /scans/{id}/confirm  body: {date, items:[{item_id, quantity}]}"""

    def post(self, request, pk):
        return not_implemented()

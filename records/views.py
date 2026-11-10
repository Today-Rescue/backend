from common.responses import not_implemented
from rest_framework.views import APIView


class RecordListView(APIView):
    """GET /stores/{id}/records?date="""

    def get(self, request, store_id):
        return not_implemented()


class RecordUpsertView(APIView):
    """PUT /stores/{id}/records/{date}  body: [{item_id, made_qty, left_qty, sold_out}]"""

    def put(self, request, store_id, date):
        return not_implemented()


class CalendarView(APIView):
    """GET /stores/{id}/records/calendar?month=2026-11"""

    def get(self, request, store_id):
        return not_implemented()

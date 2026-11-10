from common.responses import not_implemented
from rest_framework.views import APIView


class UploadView(APIView):
    """POST /uploads  (multipart: file) → {url}"""

    def post(self, request):
        return not_implemented()

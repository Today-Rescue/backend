from rest_framework.views import APIView

from common.responses import ok

from .services import reset_demo


class DemoResetView(APIView):
    """POST /demo/reset"""

    def post(self, request):
        reset_demo()
        return ok()

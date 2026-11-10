from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler


class AppError(APIException):
    """서비스 에러. raise AppError("ITEM_NOT_FOUND", "품목을 찾을 수 없어요", 404)"""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, code: str, message: str, status_code: int | None = None):
        self.code = code
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail=message, code=code)


class ExternalAPIError(AppError):
    """외부 API(기상청, 카카오, Claude) 실패 → 502"""

    def __init__(self, code: str = "EXTERNAL_API_ERROR", message: str = "외부 서비스 응답이 없어요"):
        super().__init__(code, message, status.HTTP_502_BAD_GATEWAY)


DEFAULT_CODES = {
    400: ("INVALID_INPUT", "입력값을 확인해 주세요"),
    404: ("NOT_FOUND", "찾을 수 없어요"),
    405: ("METHOD_NOT_ALLOWED", "허용되지 않은 요청이에요"),
    502: ("EXTERNAL_API_ERROR", "외부 서비스 응답이 없어요"),
}


def custom_exception_handler(exc, context):
    """모든 에러를 {"code", "message"} 형식으로 통일"""
    response = exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, AppError):
        response.data = {"code": exc.code, "message": exc.message}
        return response

    code, message = DEFAULT_CODES.get(response.status_code, ("ERROR", "요청을 처리하지 못했어요"))
    data = {"code": code, "message": message}
    if response.status_code == 400:
        data["detail"] = response.data  # 필드별 검증 에러
    response.data = data
    return response

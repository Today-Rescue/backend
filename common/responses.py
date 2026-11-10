from rest_framework import status
from rest_framework.response import Response


def ok():
    return Response({"ok": True})


def error(code: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
    return Response({"code": code, "message": message}, status=status_code)


def not_implemented():
    """아직 안 만든 API 자리 표시용"""
    return error("NOT_IMPLEMENTED", "아직 준비 중이에요", status.HTTP_501_NOT_IMPLEMENTED)

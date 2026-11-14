"""마감 행동 타임라인 (RC-04)

다른 앱에서도 부르는 함수 (이름·모양 고정)
- log_action(store_id, type, message, detail=None, date=None): 행동 기록
- get_actions(store_id, date): 그날 타임라인 [{type, message, detail, time}]
"""
from datetime import date as date_cls

from django.utils import timezone

from .models import ActionLog

Type = ActionLog.Type


def log_action(store_id: int, type: str, message: str, detail: dict | None = None,
               date: date_cls | None = None) -> ActionLog:
    """date를 안 주면 오늘. 스캔·마감처럼 날짜를 지정해 확정하는 행동은 그 날짜를 넘겨요"""
    now = timezone.now()
    return ActionLog.objects.create(
        store_id=store_id, type=type, message=message, detail=detail or {},
        date=date or timezone.localdate(now), occurred_at=now,
    )


def get_actions(store_id: int, target: date_cls) -> list[dict]:
    rows = ActionLog.objects.filter(store_id=store_id, date=target).order_by("occurred_at", "id")
    return [
        {
            "id": a.id,
            "type": a.type,
            "message": a.message,
            "detail": a.detail,
            "time": timezone.localtime(a.occurred_at).strftime("%H:%M"),
        }
        for a in rows
    ]

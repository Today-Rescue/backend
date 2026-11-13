from django.db import models

from common.models import TimeStampedModel


class Store(TimeStampedModel):
    ALERT_HOURS_CHOICES = [(1, "1시간 전"), (2, "2시간 전"), (3, "3시간 전")]

    name = models.CharField(max_length=50)
    lat = models.FloatField(null=True)
    lng = models.FloatField(null=True)
    nx = models.IntegerField(null=True)  # 기상청 격자 X (lat, lng로 계산)
    ny = models.IntegerField(null=True)  # 기상청 격자 Y
    is_demo = models.BooleanField(default=False)

    dong = models.CharField(max_length=30, blank=True, default="")  # 예: 서교동
    open_time = models.TimeField(null=True, blank=True)
    close_time = models.TimeField(null=True, blank=True)
    closed_days = models.JSONField(default=list, blank=True)  # 예: ["mon", "sun"]
    alert_hours_before = models.PositiveSmallIntegerField(choices=ALERT_HOURS_CHOICES, default=3)

    def __str__(self):
        return self.name
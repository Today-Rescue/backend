from django.db import models

from common.models import TimeStampedModel


class WeatherDaily(TimeStampedModel):
    """Grid를 참조하지 않고 nx, ny만 저장 → A와 독립"""

    nx = models.IntegerField()
    ny = models.IntegerField()
    date = models.DateField()
    tmax = models.FloatField(null=True)
    tmin = models.FloatField(null=True)
    pop_max = models.IntegerField(null=True)  # 최대 강수확률 %
    has_rain = models.BooleanField(default=False)
    base_date = models.CharField(max_length=8)  # 어느 발표분인지
    base_time = models.CharField(max_length=4)

    class Meta:
        unique_together = ("nx", "ny", "date")


class Holiday(models.Model):
    date = models.DateField(unique=True)
    name = models.CharField(max_length=30)
    is_holiday = models.BooleanField()

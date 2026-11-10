from django.db import models

from common.models import TimeStampedModel


class Store(TimeStampedModel):
    name = models.CharField(max_length=50)
    lat = models.FloatField(null=True)
    lng = models.FloatField(null=True)
    nx = models.IntegerField(null=True)  # 기상청 격자 X (lat, lng로 계산)
    ny = models.IntegerField(null=True)  # 기상청 격자 Y
    is_demo = models.BooleanField(default=False)

    def __str__(self):
        return self.name

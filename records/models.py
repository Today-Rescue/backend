from django.db import models
from django.utils import timezone

from common.models import TimeStampedModel


class DailyRecord(TimeStampedModel):
    store = models.ForeignKey("stores.Store", on_delete=models.CASCADE)
    item = models.ForeignKey("items.Item", on_delete=models.CASCADE)
    date = models.DateField()
    made_qty = models.IntegerField(default=0)
    left_qty = models.IntegerField(null=True, blank=True)  # null = 아직 미확정
    sold_out = models.BooleanField(default=False)

    class Meta:
        unique_together = ("item", "date")


class DailyProduction(TimeStampedModel):
    """오늘 만든 수량 기록. 최초 진열 + 추가 생산이 각각 한 줄씩 쌓여요."""

    class Source(models.TextChoices):
        INITIAL = "initial", "진열 촬영"
        EXTRA = "extra", "추가 생산"
        EDIT = "edit", "직접 수정"

    store = models.ForeignKey("stores.Store", on_delete=models.CASCADE)
    item = models.ForeignKey("items.Item", on_delete=models.CASCADE)
    date = models.DateField()
    qty = models.IntegerField()  # 직접 수정은 줄일 때 음수도 가능
    source = models.CharField(max_length=10, choices=Source.choices)
    recorded_at = models.DateTimeField(default=timezone.now)


class CloseRecord(TimeStampedModel):
    """마감 처리 기록. 남은 빵을 폐기와 내일 판매로 나눠요."""

    store = models.ForeignKey("stores.Store", on_delete=models.CASCADE)
    item = models.ForeignKey("items.Item", on_delete=models.CASCADE)
    date = models.DateField()
    left_qty = models.IntegerField()  # 마감 시점 남은 수량
    disposed_qty = models.IntegerField(default=0)  # 폐기
    carryover_qty = models.IntegerField(default=0)  # 내일 판매
    closed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("item", "date")
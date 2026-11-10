from django.db import models

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

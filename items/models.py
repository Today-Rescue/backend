from django.db import models

from common.models import TimeStampedModel


class Item(TimeStampedModel):
    store = models.ForeignKey("stores.Store", on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=30)
    price = models.IntegerField()
    cost = models.IntegerField(null=True, blank=True)  # 디자인에서 빠져서 선택
    image_url = models.CharField(max_length=300, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

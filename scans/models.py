from django.db import models

from common.models import TimeStampedModel


class ShelfScan(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending"
        OK = "ok"
        TOO_DARK = "too_dark"
        NO_ITEMS = "no_items"
        ERROR = "error"
        CONFIRMED = "confirmed"

    store = models.ForeignKey("stores.Store", on_delete=models.CASCADE)
    image_url = models.CharField(max_length=300)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    llm_result = models.JSONField(null=True)
    confirmed_result = models.JSONField(null=True)

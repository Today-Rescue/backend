from django.db import models

from common.models import TimeStampedModel


class Listing(TimeStampedModel):
    class Type(models.TextChoices):
        GROUP_SALE = "group_sale"
        DONATION = "donation"

    class Status(models.TextChoices):
        RECEIVED = "received"
        CONFIRMED = "confirmed"
        COMPLETED = "completed"
        CANCELED = "canceled"

    store = models.ForeignKey("stores.Store", on_delete=models.CASCADE)
    type = models.CharField(max_length=20, choices=Type.choices)
    partner_name = models.CharField(max_length=50)  # 홍익대 학생회, 마포 나눔센터
    partner_contact = models.CharField(max_length=30, blank=True)
    pickup_date = models.DateField()
    pickup_start = models.TimeField()
    pickup_end = models.TimeField(null=True, blank=True)
    bundle_price = models.IntegerField(null=True, blank=True)  # 판매만
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED)
    memo = models.TextField(blank=True)


class ListingItem(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey("items.Item", on_delete=models.PROTECT)
    qty = models.IntegerField()

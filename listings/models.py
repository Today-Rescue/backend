"""마감 세일 (일괄 할인 SL, 세트 BX)

당근·토스 연동 없이 사장님이 앱에서 "세일을 시작했다"고 등록하는 것까지만 관리해요.
"""
from django.db import models

from common.models import TimeStampedModel


class SaleCampaign(TimeStampedModel):
    class Type(models.TextChoices):
        DISCOUNT = "discount"  # 일괄 할인
        BUNDLE = "bundle"  # 세트 (P1)

    class Status(models.TextChoices):
        ACTIVE = "active"  # 진행 중
        STOPPED = "stopped"  # 사장님이 중지
        ENDED = "ended"  # 종료 (마감)

    class Channel(models.TextChoices):
        DAANGN = "daangn"  # 당근 (표시용, 연동 없음)

    store = models.ForeignKey("stores.Store", on_delete=models.CASCADE, related_name="campaigns")
    type = models.CharField(max_length=20, choices=Type.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    discount_rate = models.IntegerField(null=True, blank=True)  # % (일괄 할인만)
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.DAANGN)
    started_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)  # 예정 종료 (보통 마감 시각)
    stopped_at = models.DateTimeField(null=True, blank=True)  # 실제 중지·종료 시각


class CampaignItem(models.Model):
    """세일 대상 품목. start_qty는 세일 시작 시점 남은 수량 (마감 때 할인 판매 수 계산용)"""

    campaign = models.ForeignKey(SaleCampaign, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey("items.Item", on_delete=models.PROTECT)
    sale_price = models.IntegerField()  # 할인가 (원)
    start_qty = models.IntegerField(null=True)  # 모르면 null

    class Meta:
        unique_together = ("campaign", "item")

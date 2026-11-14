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


class Bundle(models.Model):
    """세트(럭키박스) 정보. type=bundle 캠페인에 하나"""

    campaign = models.OneToOneField(SaleCampaign, on_delete=models.CASCADE, related_name="bundle")
    name = models.CharField(max_length=50)
    price = models.IntegerField()  # 한 팩 판매가 (원)
    packs = models.IntegerField()  # 만든 팩 수


class SalesEvent(models.Model):
    """세일 중 판매 한 건 (LV-01, RC-03, DB-02)

    - 일괄 할인: item + quantity(개)
    - 세트: item 없음, quantity = 팩 수
    """

    class Channel(models.TextChoices):
        DAANGN = "daangn"  # 당근 주문
        STORE = "store"  # 매장 결제

    campaign = models.ForeignKey(SaleCampaign, on_delete=models.CASCADE, related_name="sales")
    item = models.ForeignKey("items.Item", on_delete=models.PROTECT, null=True, blank=True)
    quantity = models.IntegerField()
    unit_price = models.IntegerField()  # 판매가 (할인가 또는 팩 가격)
    channel = models.CharField(max_length=20, choices=Channel.choices)
    sold_at = models.DateTimeField(auto_now_add=True)


class BundleItem(models.Model):
    bundle = models.ForeignKey(Bundle, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey("items.Item", on_delete=models.PROTECT)
    per_pack = models.IntegerField()  # 팩당 개수

    class Meta:
        unique_together = ("bundle", "item")


class ActionLog(models.Model):
    """마감 행동 기록 (RC-04 타임라인). listings.actions.log_action으로 남겨요"""

    class Type(models.TextChoices):
        SCAN = "scan"  # 스캔 확정 (최초 진열 / 재고 기록)
        SALE_START = "sale_start"  # 일괄 할인 시작
        BUNDLE_START = "bundle_start"  # 세트 등록
        SALE_UPDATE = "sale_update"  # 할인율·품목 변경
        SALE_STOP = "sale_stop"  # 세일 중지·종료
        CLOSE = "close"  # 마감 기록 저장

    store = models.ForeignKey("stores.Store", on_delete=models.CASCADE, related_name="actions")
    date = models.DateField()  # 영업일
    type = models.CharField(max_length=20, choices=Type.choices)
    message = models.CharField(max_length=100)  # 화면에 보여줄 한 줄
    detail = models.JSONField(default=dict, blank=True)  # 예: {"campaign_id": 7, "from": 30, "to": 40}
    occurred_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["store", "date"])]

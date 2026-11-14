from django.db import models

from common.models import TimeStampedModel


class ShelfScan(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending"
        OK = "ok"  # 모든 품목 인식
        PARTIAL = "partial"  # 일부 품목만 인식 (CP-05)
        FAILED = "failed"  # 찾은 품목 없음 (CP-06)
        TIMEOUT = "timeout"  # 20초 초과 또는 AI 통신 실패 (CP-04)
        TOO_DARK = "too_dark"  # 사진 어두움 (CP-07)
        CONFIRMED = "confirmed"  # 수량 확정 완료

    class Purpose(models.TextChoices):
        OPEN = "open"  # 최초 진열 → 오늘 만든 수량 (PR-02)
        CLOSE = "close"  # 재고 기록 → 남은 수량 (SR)

    store = models.ForeignKey("stores.Store", on_delete=models.CASCADE)
    purpose = models.CharField(max_length=10, choices=Purpose.choices, default=Purpose.CLOSE)
    image_url = models.CharField(max_length=300)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    model_name = models.CharField(max_length=50, blank=True)  # 인식에 쓴 AI 모델
    llm_result = models.JSONField(null=True)  # AI 원본 응답
    confirmed_result = models.JSONField(null=True)


class ScanCount(models.Model):
    """스캔의 품목별 인식 수량·확정 수량 (수정 전후 값 = 학습 데이터)"""

    scan = models.ForeignKey(ShelfScan, on_delete=models.CASCADE, related_name="counts")
    item = models.ForeignKey("items.Item", on_delete=models.CASCADE)
    detected_qty = models.IntegerField(null=True)  # AI가 센 수량. 못 찾았으면 null
    confidence = models.FloatField(null=True)  # 0~1
    confirmed_qty = models.IntegerField(null=True)  # 사장님이 확정한 수량

    class Meta:
        unique_together = ("scan", "item")

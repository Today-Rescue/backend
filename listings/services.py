from datetime import datetime

from django.db import transaction
from django.utils import timezone

from common.exceptions import AppError
from items.models import Item
from records.models import DailyRecord
from scans.models import ScanCount

from .models import CampaignItem, SaleCampaign

DISCOUNT_RATES = (20, 30, 40, 50)


def sale_price(price: int, rate: int) -> int:
    """할인가. 10원 단위 버림"""
    return price * (100 - rate) // 100 // 10 * 10


def current_left_qty(store_id: int, item_ids: list[int]) -> dict[int, int]:
    """품목별 지금 남은 수량. 오늘 마지막 확정 스캔 → 없으면 오늘 일일 기록의 남은 수량"""
    today = timezone.localdate()
    result: dict[int, int] = {}
    counts = (
        ScanCount.objects.filter(scan__store_id=store_id, item_id__in=item_ids,
                                 confirmed_qty__isnull=False, scan__updated_at__date=today)
        .order_by("scan__updated_at")
    )
    for c in counts:  # 오래된 것부터 덮어써서 마지막 값이 남음
        result[c.item_id] = c.confirmed_qty
    records = DailyRecord.objects.filter(store_id=store_id, item_id__in=item_ids, date=today,
                                         left_qty__isnull=False)
    for r in records:
        result.setdefault(r.item_id, r.left_qty)
    return result


def _store_items(store_id: int, item_ids: list[int]) -> list[Item]:
    if len(item_ids) != len(set(item_ids)):
        raise AppError("DUPLICATE_ITEM", "같은 품목이 두 번 들어 있어요")
    items = list(Item.objects.filter(store_id=store_id, id__in=item_ids, is_active=True))
    if len(items) != len(item_ids):
        raise AppError("INVALID_ITEM", "이 가게의 품목이 아니에요")
    return items


def active_discount(store_id: int) -> SaleCampaign | None:
    return SaleCampaign.objects.filter(
        store_id=store_id, type=SaleCampaign.Type.DISCOUNT, status=SaleCampaign.Status.ACTIVE
    ).first()


@transaction.atomic
def start_discount(store, rate: int, item_ids: list[int], ends_at: datetime | None) -> SaleCampaign:
    """일괄 할인 시작 (SL-05). 가게당 진행 중인 일괄 할인은 1개"""
    if active_discount(store.id):
        raise AppError("DISCOUNT_ALREADY_ACTIVE", "이미 진행 중인 할인이 있어요")
    items = _store_items(store.id, item_ids)
    now = timezone.now()
    if ends_at and ends_at <= now:
        raise AppError("INVALID_END_TIME", "종료 시각은 지금 이후여야 해요")

    campaign = SaleCampaign.objects.create(
        store=store, type=SaleCampaign.Type.DISCOUNT, discount_rate=rate,
        started_at=now, ends_at=ends_at,
    )
    left = current_left_qty(store.id, item_ids)
    CampaignItem.objects.bulk_create([
        CampaignItem(campaign=campaign, item=it, sale_price=sale_price(it.price, rate),
                     start_qty=left.get(it.id))
        for it in items
    ])
    return campaign


def _ensure_active(campaign: SaleCampaign) -> None:
    if campaign.status != SaleCampaign.Status.ACTIVE:
        raise AppError("CAMPAIGN_NOT_ACTIVE", "진행 중인 세일이 아니에요")


@transaction.atomic
def update_discount(campaign: SaleCampaign, rate: int | None, item_ids: list[int] | None) -> SaleCampaign:
    """할인율·대상 품목 변경 (SL 화면 [할인율·품목 변경], LV-04 할인율 올리기)"""
    _ensure_active(campaign)
    if rate is not None:
        campaign.discount_rate = rate
        campaign.save(update_fields=["discount_rate", "updated_at"])

    if item_ids is not None:
        items = _store_items(campaign.store_id, item_ids)
        existing = {ci.item_id: ci for ci in campaign.items.all()}
        campaign.items.exclude(item_id__in=item_ids).delete()
        new_ids = [it.id for it in items if it.id not in existing]
        left = current_left_qty(campaign.store_id, new_ids)
        CampaignItem.objects.bulk_create([
            CampaignItem(campaign=campaign, item=it, sale_price=0, start_qty=left.get(it.id))
            for it in items if it.id in new_ids
        ])

    for ci in campaign.items.select_related("item"):  # 할인가 다시 계산
        ci.sale_price = sale_price(ci.item.price, campaign.discount_rate)
        ci.save(update_fields=["sale_price"])
    return campaign


def stop_campaign(campaign: SaleCampaign, status: str) -> SaleCampaign:
    """중지(stopped) 또는 종료(ended)"""
    _ensure_active(campaign)
    campaign.status = status
    campaign.stopped_at = timezone.now()
    campaign.save(update_fields=["status", "stopped_at", "updated_at"])
    return campaign


def campaign_response(campaign: SaleCampaign) -> dict:
    items = []
    for ci in campaign.items.select_related("item").order_by("item_id"):
        items.append({
            "item_id": ci.item_id,
            "name": ci.item.name,
            "image_url": ci.item.image_url,
            "price": ci.item.price,
            "sale_price": ci.sale_price,
            "start_qty": ci.start_qty,
        })
    return {
        "id": campaign.id,
        "type": campaign.type,
        "status": campaign.status,
        "discount_rate": campaign.discount_rate,
        "channel": campaign.channel,
        "started_at": timezone.localtime(campaign.started_at).isoformat(timespec="minutes"),
        "ends_at": timezone.localtime(campaign.ends_at).isoformat(timespec="minutes") if campaign.ends_at else None,
        "stopped_at": timezone.localtime(campaign.stopped_at).isoformat(timespec="minutes") if campaign.stopped_at else None,
        # SL-03 요약
        "item_count": len(items),
        "total_qty": sum(x["start_qty"] or 0 for x in items),
        "items": items,
    }

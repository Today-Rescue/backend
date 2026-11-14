from datetime import datetime

from django.db import transaction
from django.utils import timezone

from common.exceptions import AppError
from items.models import Item
from records.models import DailyRecord
from scans.models import RiskSnapshot, ScanCount, ShelfScan
from scans.services import latest_risks

from . import bundles, clients
from .models import Bundle, BundleItem, CampaignItem, SaleCampaign, SalesEvent

DISCOUNT_RATES = (20, 30, 40, 50)
RISK_TARGETS = {RiskSnapshot.Level.DANGER, RiskSnapshot.Level.CAUTION}


def sale_price(price: int, rate: int) -> int:
    """할인가. 10원 단위 버림"""
    return price * (100 - rate) // 100 // 10 * 10


def current_left_qty(store_id: int, item_ids: list[int]) -> dict[int, int]:
    """품목별 지금 남은 수량. 오늘 마지막 확정 재고 스캔(close) → 없으면 오늘 일일 기록의 남은 수량

    오전 진열 스캔(open)은 만든 수량이라 제외
    """
    today = timezone.localdate()
    result: dict[int, int] = {}
    counts = (
        ScanCount.objects.filter(scan__store_id=store_id, item_id__in=item_ids,
                                 scan__purpose=ShelfScan.Purpose.CLOSE,
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


def default_ends_at(store) -> datetime | None:
    """세일 종료 기본값 = 오늘 마감 시각 (SL-04 '지금 ~ 마감'). 이미 지났거나 모르면 None"""
    if store.close_time is None:
        return None
    now = timezone.localtime()
    closes = timezone.make_aware(datetime.combine(now.date(), store.close_time))
    return closes if closes > now else None


def risk_item_ids(store_id: int) -> list[int]:
    """오늘 마지막 재고 스캔의 위험·주의 품목 (MN-05 원터치 할인 대상)"""
    risks = latest_risks(store_id, timezone.localdate())
    if not risks:
        raise AppError("NO_STOCK_SCAN", "먼저 매대를 찍어 남은 재고를 확인해 주세요")
    ids = [i for i, r in risks.items() if r.level in RISK_TARGETS]
    if not ids:
        raise AppError("NO_RISK_ITEMS", "할인이 필요한 위험·주의 품목이 없어요")
    return sorted(ids)


def discount_options(store, rate: int) -> list[dict]:
    """할인 화면(SL-02) 품목 체크리스트. 위험·주의는 기본 선택, 여유는 해제"""
    risks = latest_risks(store.id, timezone.localdate())
    items = list(Item.objects.filter(store=store, is_active=True).order_by("id"))
    left = current_left_qty(store.id, [it.id for it in items])
    rows = []
    for it in items:
        r = risks.get(it.id)
        rows.append({
            "item_id": it.id,
            "name": it.name,
            "image_url": it.image_url,
            "price": it.price,
            "sale_price": sale_price(it.price, rate),
            "left_qty": left.get(it.id),
            "level": r.level if r else None,
            "reason": r.reason if r else None,
            "default_selected": bool(r and r.level in RISK_TARGETS),
        })
    order = {"danger": 0, "caution": 1, "safe": 2, None: 3}
    rows.sort(key=lambda x: order[x["level"]])
    return rows


@transaction.atomic
def start_discount(store, rate: int, item_ids: list[int] | None, ends_at: datetime | None) -> SaleCampaign:
    """일괄 할인 시작 (SL-05). 가게당 진행 중인 일괄 할인은 1개

    item_ids가 없으면 원터치 할인 (MN-05): 마지막 재고 스캔의 위험·주의 품목
    ends_at이 없으면 오늘 마감 시각
    """
    if active_discount(store.id):
        raise AppError("DISCOUNT_ALREADY_ACTIVE", "이미 진행 중인 할인이 있어요")
    if not item_ids:
        item_ids = risk_item_ids(store.id)
    items = _store_items(store.id, item_ids)
    now = timezone.now()
    if ends_at and ends_at <= now:
        raise AppError("INVALID_END_TIME", "종료 시각은 지금 이후여야 해요")
    ends_at = ends_at or default_ends_at(store)

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
    if campaign.type != SaleCampaign.Type.DISCOUNT:
        raise AppError("NOT_DISCOUNT", "일괄 할인만 수정할 수 있어요")
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
    bundle = None
    if campaign.type == SaleCampaign.Type.BUNDLE and hasattr(campaign, "bundle"):
        b = campaign.bundle
        bundle = {
            "name": b.name,
            "price": b.price,
            "packs": b.packs,
            "composition": [{"item_id": bi.item_id, "name": bi.item.name, "per_pack": bi.per_pack}
                            for bi in b.items.select_related("item").order_by("item_id")],
        }
    return {
        "id": campaign.id,
        "type": campaign.type,
        "bundle": bundle,
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


# ── 세트 (BX) ─────────────────────────────────────────
def _bundle_stocks(store_id: int, rows: list[dict]) -> tuple[dict[int, Item], dict[int, int]]:
    """[{item_id, qty?}] → (품목, 재고). qty가 없으면 지금 남은 수량으로"""
    items = {it.id: it for it in _store_items(store_id, [r["item_id"] for r in rows])}
    left = current_left_qty(store_id, list(items))
    stocks = {}
    for r in rows:
        qty = r.get("qty")
        if qty is None:
            qty = left.get(r["item_id"])
        if qty is None:
            raise AppError("STOCK_UNKNOWN", f"{items[r['item_id']].name}의 남은 수량을 알 수 없어요")
        stocks[r["item_id"]] = qty
    return items, stocks


def _composition_response(items: dict[int, Item], stocks: dict[int, int], comp: dict) -> dict:
    prices = {i: items[i].price for i in comp["per_pack"]}
    unit_total, rec_price = bundles.recommended_price(prices, comp["per_pack"])
    return {
        "items": [
            {"item_id": i, "name": items[i].name, "price": items[i].price, "stock": stocks[i],
             "per_pack": comp["per_pack"][i], "leftover": comp["leftover_by_item"][i]}
            for i in sorted(comp["per_pack"])
        ],
        "packs": comp["packs"],
        "leftover": comp["leftover"],
        "unit_total": unit_total,  # 한 팩 단품 판매가 합계
        "recommended_price": rec_price,
    }


def _default_name(items: dict[int, Item], per_pack: dict[int, int]) -> str:
    return "·".join(items[i].name for i in sorted(per_pack)) + " 럭키박스"


def recommend_bundles(store, item_ids: list[int] | None) -> list[dict]:
    """추천 세트 (BX-01). item_ids를 주면 그 품목으로 1개, 없으면 재고 많은 품목 위주로 최대 3개"""
    if item_ids:
        items, stocks = _bundle_stocks(store.id, [{"item_id": i} for i in item_ids])
        comp = bundles.best_composition(stocks)
        comps = [comp] if comp else []
    else:
        all_items = list(Item.objects.filter(store=store, is_active=True))
        items = {it.id: it for it in all_items}
        stocks = current_left_qty(store.id, list(items))
        comps = bundles.candidate_sets(stocks)
    if not comps:
        raise AppError("BUNDLE_NOT_POSSIBLE", "세트를 만들 만큼 남은 빵이 없어요")

    results = [_composition_response(items, stocks, c) for c in comps]
    names = clients.generate_names([
        [f"{x['name']} {x['per_pack']}개" for x in r["items"]] for r in results
    ])
    for r, c, i in zip(results, comps, range(len(results))):
        r["name"] = names[i] if names else _default_name(items, c["per_pack"])
    return results


def calculate_bundle(store, rows: list[dict]) -> dict:
    """사장님이 고른 구성 계산 (BX-02, BX-03) + 더 적게 남는 구성이 있으면 better로"""
    items, stocks = _bundle_stocks(store.id, rows)
    per_pack = {r["item_id"]: r["per_pack"] for r in rows}
    current = bundles.evaluate(stocks, per_pack)
    result = _composition_response(items, stocks, {"per_pack": per_pack, **current})
    best = bundles.best_composition(stocks)
    better = None
    if best and (best["leftover"], -best["packs"]) < (current["leftover"], -current["packs"]):
        better = _composition_response(items, stocks, best)
    result["better"] = better
    return result


@transaction.atomic
def start_bundle(store, name: str, price: int, rows: list[dict], ends_at: datetime | None) -> SaleCampaign:
    """세트 판매 시작 (BX-05)"""
    items, stocks = _bundle_stocks(store.id, rows)
    per_pack = {r["item_id"]: r["per_pack"] for r in rows}
    packs = bundles.evaluate(stocks, per_pack)["packs"]
    if packs < 1:
        raise AppError("BUNDLE_NOT_POSSIBLE", "남은 빵으로 한 팩도 만들 수 없어요")
    now = timezone.now()
    if ends_at and ends_at <= now:
        raise AppError("INVALID_END_TIME", "종료 시각은 지금 이후여야 해요")

    campaign = SaleCampaign.objects.create(store=store, type=SaleCampaign.Type.BUNDLE,
                                           started_at=now, ends_at=ends_at)
    CampaignItem.objects.bulk_create([
        CampaignItem(campaign=campaign, item=items[i], sale_price=items[i].price, start_qty=stocks[i])
        for i in per_pack
    ])
    bundle = Bundle.objects.create(campaign=campaign, name=name, price=price, packs=packs)
    BundleItem.objects.bulk_create([BundleItem(bundle=bundle, item=items[i], per_pack=n) for i, n in per_pack.items()])
    return campaign


# ── 판매 기록 (#21) ───────────────────────────────────
def _apply_sale(store_id: int, sale_date, item_id: int, qty: int) -> None:
    """records.services.apply_sale (A) 호출. 아직 없으면 준비 중 에러 → 판매 기록도 취소"""
    from records import services as records_services

    apply_sale = getattr(records_services, "apply_sale", None)
    if apply_sale is None:
        raise AppError("APPLY_SALE_NOT_READY", "남은 수량 차감은 아직 준비 중이에요", 501)
    apply_sale(store_id, sale_date, item_id, qty)


def sold_by_item(campaign: SaleCampaign) -> dict[int | None, int]:
    """{item_id: 판매 수}. 세트 판매(팩 수)는 None 키"""
    result: dict[int | None, int] = {}
    for item_id, qty in campaign.sales.values_list("item_id", "quantity"):
        result[item_id] = result.get(item_id, 0) + qty
    return result


@transaction.atomic
def record_sales(campaign: SaleCampaign, channel: str, items: list[dict] | None, packs: int | None) -> list[SalesEvent]:
    """판매 확정 (POST /campaigns/{id}/sales)

    - 일괄 할인: items=[{item_id, quantity}] → 품목별 apply_sale
    - 세트: packs → 구성 품목마다 팩 수 × 팩당 개수만큼 apply_sale
    세일 시작 때 남은 수량(start_qty)이나 팩 수보다 많이 팔 수 없음
    """
    campaign = SaleCampaign.objects.select_for_update().get(pk=campaign.pk)
    _ensure_active(campaign)
    sale_date = timezone.localtime(campaign.started_at).date()
    sold = sold_by_item(campaign)
    events = []

    if campaign.type == SaleCampaign.Type.BUNDLE:
        if not packs:
            raise AppError("PACKS_REQUIRED", "판매한 팩 수를 보내 주세요")
        bundle = campaign.bundle
        if sold.get(None, 0) + packs > bundle.packs:
            raise AppError("OVER_STOCK", f"남은 팩은 {bundle.packs - sold.get(None, 0)}팩이에요")
        events.append(SalesEvent.objects.create(campaign=campaign, quantity=packs, unit_price=bundle.price,
                                                channel=channel))
        for bi in bundle.items.all():
            _apply_sale(campaign.store_id, sale_date, bi.item_id, packs * bi.per_pack)
        return events

    if not items:
        raise AppError("ITEMS_REQUIRED", "판매한 품목을 보내 주세요")
    targets = {ci.item_id: ci for ci in campaign.items.select_related("item")}
    seen = set()
    for row in items:
        item_id, qty = row["item_id"], row["quantity"]
        if item_id in seen:
            raise AppError("DUPLICATE_ITEM", "같은 품목이 두 번 들어 있어요")
        seen.add(item_id)
        ci = targets.get(item_id)
        if ci is None:
            raise AppError("ITEM_NOT_IN_CAMPAIGN", "할인 대상 품목이 아니에요")
        if ci.start_qty is not None and sold.get(item_id, 0) + qty > ci.start_qty:
            raise AppError("OVER_STOCK", f"{ci.item.name}은(는) {ci.start_qty - sold.get(item_id, 0)}개 남았어요")
        events.append(SalesEvent.objects.create(campaign=campaign, item_id=item_id, quantity=qty,
                                                unit_price=ci.sale_price, channel=channel))
        _apply_sale(campaign.store_id, sale_date, item_id, qty)
    return events


def sale_response(e: SalesEvent) -> dict:
    return {
        "id": e.id,
        "item_id": e.item_id,
        "name": e.item.name if e.item_id else e.campaign.bundle.name,
        "quantity": e.quantity,
        "unit": "item" if e.item_id else "pack",
        "unit_price": e.unit_price,
        "amount": e.unit_price * e.quantity,
        "channel": e.channel,
        "sold_at": timezone.localtime(e.sold_at).isoformat(timespec="minutes"),
    }

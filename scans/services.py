import io
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageStat

from common.exceptions import AppError
from items.models import Item
from records.services import update_left_qty
from uploads.services import resize_image, save_bytes

from . import clients, risk
from .models import RiskSnapshot, ScanCount, ShelfScan

PROMPT_PATH = Path(__file__).parent / "prompts" / "shelf_scan.txt"
DARK_THRESHOLD = 35  # 평균 밝기(0~255)가 이보다 낮으면 AI 호출 없이 too_dark
TIME_LIMIT = 20  # 초. 넘으면 timeout (CP-04)
CONFIDENCE_THRESHOLD = 0.7  # 이보다 낮으면 "개수 확인 필요" (SR-06)

Status = ShelfScan.Status
Purpose = ShelfScan.Purpose
CONFIRMABLE = {Status.OK, Status.PARTIAL, Status.FAILED, Status.TIMEOUT, Status.TOO_DARK}


def recommended_purpose(store, now: datetime | None = None) -> str:
    """촬영 목적 추천 (CP-01). 마감 알림 시각 전이면 open, 이후면 close. 마감 시각이 없으면 close"""
    if store.close_time is None:
        return Purpose.CLOSE
    now = timezone.localtime(now)
    alert_at = datetime.combine(now.date(), store.close_time) - timedelta(hours=store.alert_hours_before)
    return Purpose.OPEN if now.replace(tzinfo=None) < alert_at else Purpose.CLOSE


def load_prompt(items) -> str:
    item_lines = "\n".join(f"- item_id={it.id}: {it.name}" for it in items)
    return PROMPT_PATH.read_text(encoding="utf-8").replace("{items}", item_lines)


def is_too_dark(image_bytes: bytes) -> bool:
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    return ImageStat.Stat(img).mean[0] < DARK_THRESHOLD


def parse_result(raw: dict, valid_ids: set[int]) -> tuple[str, dict[int, dict]]:
    """AI 응답 검증 → (AI status, {item_id: {quantity, confidence}})

    가게에 없는 item_id는 버리고, 같은 품목이 여러 번 오면 합치고(확신도는 낮은 쪽), 음수는 0
    """
    status = raw.get("status")
    if status not in ("ok", "too_dark", "no_items"):
        raise ValueError(f"invalid status: {status}")

    found: dict[int, dict] = {}
    for row in raw.get("items") or []:
        item_id = int(row["item_id"])
        if item_id not in valid_ids:
            continue
        qty = max(int(row["quantity"]), 0)
        conf = min(max(float(row["confidence"]), 0.0), 1.0)
        if item_id in found:
            found[item_id]["quantity"] += qty
            found[item_id]["confidence"] = min(found[item_id]["confidence"], conf)
        else:
            found[item_id] = {"quantity": qty, "confidence": conf}
    return status, found


def scan_status(ai_status: str, found: dict, total: int) -> str:
    if ai_status == "too_dark":
        return Status.TOO_DARK
    if not found:
        return Status.FAILED
    return Status.OK if len(found) == total else Status.PARTIAL


def create_scan(store, image_file, purpose: str | None = None) -> ShelfScan:
    """사진 저장 → 밝기 확인 → AI 인식(20초 제한) → 품목별 ScanCount 저장

    purpose를 안 보내면 지금 시각 기준 추천 목적으로 저장
    """
    items = list(Item.objects.filter(store=store, is_active=True).order_by("id"))
    if not items:
        raise AppError("NO_STORE_ITEMS", "먼저 판매 품목을 등록해 주세요")

    image_bytes = resize_image(image_file)
    scan = ShelfScan.objects.create(
        store=store,
        purpose=purpose or recommended_purpose(store),
        image_url=save_bytes(image_bytes, "scans"),
    )

    found: dict[int, dict] = {}
    if is_too_dark(image_bytes):
        scan.status = Status.TOO_DARK
        scan.llm_result = {"checked_by": "brightness"}
    else:
        deadline = time.monotonic() + TIME_LIMIT
        prompt = load_prompt(items)
        valid_ids = {it.id for it in items}
        scan.status = Status.TIMEOUT
        while time.monotonic() < deadline:  # 응답 형식이 틀리면 남은 시간 안에서 다시
            try:
                raw, model = clients.analyze_shelf(image_bytes, prompt, deadline)
                ai_status, found = parse_result(raw, valid_ids)
            except clients.AITimeout:
                break
            except (ValueError, KeyError, TypeError) as e:
                scan.llm_result = {"error": str(e)}
                continue
            scan.status = scan_status(ai_status, found, len(items))
            scan.model_name = model
            scan.llm_result = raw
            break

    with transaction.atomic():
        scan.save()
        ScanCount.objects.bulk_create([
            ScanCount(
                scan=scan,
                item=it,
                detected_qty=found[it.id]["quantity"] if it.id in found else None,
                confidence=found[it.id]["confidence"] if it.id in found else None,
            )
            for it in items
        ])
    return scan


def scan_response(scan: ShelfScan, quantities: dict[int, int] | None = None) -> dict:
    """프론트 응답용. items는 가게 전체 품목

    - 정렬: 못 찾은 품목 맨 위 (CP-05) → 위험 → 주의 → 여유 (SR-04)
    - 재고 스캔(close)이면 품목별 위험도와 risk_summary(SR-03)를 함께 내려줌. open이면 null
    - quantities를 주면 그 수량으로 다시 계산 (SR-02 수정 즉시 재계산)
    """
    counts = list(scan.counts.select_related("item").order_by("item_id"))
    items = []
    for c in counts:
        found = c.detected_qty is not None
        qty = c.confirmed_qty if c.confirmed_qty is not None else (c.detected_qty or 0)
        if quantities and c.item_id in quantities:
            qty = quantities[c.item_id]
        items.append({
            "item_id": c.item_id,
            "name": c.item.name,
            "image_url": c.item.image_url,
            "shelf_life": c.item.shelf_life,
            "found": found,
            "quantity": qty,
            "detected_qty": c.detected_qty,
            "confidence": c.confidence,
            "needs_check": (not found) or c.confidence < CONFIDENCE_THRESHOLD,
            "level": None,
            "expected_left": None,
            "reason": None,
        })

    summary = None
    if scan.purpose == Purpose.CLOSE:
        qty_map = {x["item_id"]: x["quantity"] for x in items}
        risks = risk.evaluate(scan.store, scan.created_at, [c.item for c in counts], qty_map)
        for x in items:
            r = risks[x["item_id"]]
            x.update(level=r.level, expected_left=r.expected_left, reason=r.reason)
        summary = risk.summarize(risks, qty_map)
        items.sort(key=lambda x: (x["found"], risk.LEVEL_ORDER[x["level"]]))
    else:
        items.sort(key=lambda x: x["found"])  # 안정 정렬이라 나머지 순서 유지

    found_count = sum(1 for x in items if x["found"])
    return {
        "scan_id": scan.id,
        "purpose": scan.purpose,
        "status": scan.status,
        "image_url": scan.image_url,
        "scanned_at": timezone.localtime(scan.created_at).isoformat(timespec="minutes"),
        "found_count": found_count,
        "total_count": len(items),
        "total_quantity": sum(x["quantity"] for x in items),
        "risk_summary": summary,
        "items": items,
    }


def latest_risks(store_id: int, target: date) -> dict[int, RiskSnapshot]:
    """그날 마지막으로 확정한 재고 스캔(close)의 품목별 위험도. 없으면 {}"""
    scan = (
        ShelfScan.objects.filter(store_id=store_id, purpose=Purpose.CLOSE, status=Status.CONFIRMED,
                                 created_at__date=target)
        .order_by("-created_at")
        .first()
    )
    if not scan:
        return {}
    return {r.item_id: r for r in scan.risks.all()}


def save_risks(scan: ShelfScan, quantities: dict[int, int]) -> None:
    """확정 수량 기준 위험도 저장 (원터치 할인 대상 선택에 사용)"""
    counts = {c.item_id: c for c in scan.counts.select_related("item")}
    qty_map = {i: quantities.get(i, c.confirmed_qty or 0) for i, c in counts.items()}
    risks = risk.evaluate(scan.store, scan.created_at, [c.item for c in counts.values()], qty_map)
    RiskSnapshot.objects.filter(scan=scan).delete()
    RiskSnapshot.objects.bulk_create([
        RiskSnapshot(scan=scan, item_id=i, expected_left=r.expected_left, level=r.level, reason=r.reason)
        for i, r in risks.items()
    ])


@transaction.atomic
def confirm_scan(scan: ShelfScan, target_date: date, items: list[dict], purpose: str | None = None) -> None:
    """사장님이 확인·수정한 수량 확정 → ScanCount.confirmed_qty 저장 + 목적별 기록

    - open: records.production.add_productions (오늘 만든 수량, 출처 initial)
    - close: records.services.update_left_qty (남은 수량)
    purpose를 보내면 촬영 때 고른 목적을 바꿔서 확정 (CP-01 '목적 · 바꾸기')
    인식 실패·시간 초과여도 직접 입력한 수량으로 확정할 수 있음 (CP-04, CP-06)
    """
    if scan.status == Status.CONFIRMED:
        raise AppError("SCAN_ALREADY_CONFIRMED", "이미 확정한 사진이에요")
    if scan.status not in CONFIRMABLE:
        raise AppError("SCAN_NOT_CONFIRMABLE", "확정할 수 없는 사진이에요")

    counts = {c.item_id: c for c in scan.counts.all()}
    quantities = {}
    for row in items:
        if row["item_id"] not in counts:
            raise AppError("ITEM_NOT_FOUND", "품목을 찾을 수 없어요", 404)
        quantities[row["item_id"]] = row["quantity"]

    for item_id, qty in quantities.items():
        c = counts[item_id]
        c.confirmed_qty = qty
        c.save(update_fields=["confirmed_qty"])

    if purpose:
        scan.purpose = purpose
    if scan.purpose == Purpose.OPEN:
        try:
            from records.production import add_productions  # #17 (A)
        except ImportError:
            raise AppError("PRODUCTION_NOT_READY", "오전 진열 기록은 아직 준비 중이에요", 501)
        add_productions(scan.store_id, target_date, "initial",
                        [{"item_id": i, "qty": q} for i, q in quantities.items()])
    else:
        update_left_qty(scan.store_id, target_date, quantities)
        save_risks(scan, quantities)
    scan.status = Status.CONFIRMED
    scan.confirmed_result = {"date": target_date.isoformat()}
    scan.save()

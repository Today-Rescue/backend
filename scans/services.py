import io
from datetime import date
from pathlib import Path

from django.db import transaction
from PIL import Image, ImageStat

from common.exceptions import AppError
from items.models import Item
from records.services import update_left_qty
from uploads.services import resize_image, save_bytes

from . import clients
from .models import ShelfScan

PROMPT_PATH = Path(__file__).parent / "prompts" / "shelf_scan.txt"
DARK_THRESHOLD = 35  # 평균 밝기(0~255)가 이보다 낮으면 AI 호출 없이 too_dark


def load_prompt(items) -> str:
    item_lines = "\n".join(f"- item_id={it.id}: {it.name}" for it in items)
    return PROMPT_PATH.read_text(encoding="utf-8").replace("{items}", item_lines)


def is_too_dark(image_bytes: bytes) -> bool:
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    return ImageStat.Stat(img).mean[0] < DARK_THRESHOLD


def clean_result(raw: dict, items) -> tuple[str, list[dict]]:
    """AI 응답 검증 → (status, 가게 전체 품목별 결과)

    - 가게에 없는 item_id는 버림, 같은 품목이 여러 번 오면 합침
    - 음수는 0으로
    - 사진에서 못 찾은 품목은 quantity 0 (found=False)
    """
    status = raw.get("status")
    if status not in (ShelfScan.Status.OK, ShelfScan.Status.TOO_DARK, ShelfScan.Status.NO_ITEMS):
        raise ValueError(f"invalid status: {status}")

    found: dict[int, dict] = {}
    valid_ids = {it.id for it in items}
    for row in raw.get("items") or []:
        item_id = int(row["item_id"])
        if item_id not in valid_ids:
            continue
        qty = max(int(row["quantity"]), 0)
        prev = found.get(item_id)
        if prev:
            prev["quantity"] += qty
            prev["uncertain"] = prev["uncertain"] or bool(row.get("uncertain"))
        else:
            found[item_id] = {"quantity": qty, "uncertain": bool(row.get("uncertain"))}

    if status == ShelfScan.Status.OK and not found:
        status = ShelfScan.Status.NO_ITEMS
    if status != ShelfScan.Status.OK:
        return status, []

    result = []
    for it in items:
        f = found.get(it.id)
        result.append({
            "item_id": it.id,
            "name": it.name,
            "image_url": it.image_url,
            "quantity": f["quantity"] if f else 0,
            "uncertain": f["uncertain"] if f else False,
            "found": bool(f),
        })
    return status, result


def create_scan(store, image_file) -> ShelfScan:
    """사진 저장 → 밝기 확인 → AI 인식 → 검증(실패 시 다음 모델로 1번 더) → ShelfScan 저장"""
    items = list(Item.objects.filter(store=store, is_active=True).order_by("id"))
    if not items:
        raise AppError("NO_STORE_ITEMS", "먼저 판매 품목을 등록해 주세요")

    image_bytes = resize_image(image_file)
    scan = ShelfScan.objects.create(store=store, image_url=save_bytes(image_bytes, "scans"))

    if is_too_dark(image_bytes):
        scan.status = ShelfScan.Status.TOO_DARK
        scan.llm_result = {"items": [], "checked_by": "brightness"}
        scan.save()
        return scan

    prompt = load_prompt(items)
    last_error = None
    for _ in range(2):  # 응답 형식이 틀리면 한 번 더
        try:
            raw, model = clients.analyze_shelf(image_bytes, prompt)
            status, result = clean_result(raw, items)
            break
        except (ValueError, KeyError, TypeError) as e:
            last_error = e
        except AppError:
            scan.status = ShelfScan.Status.ERROR
            scan.save()
            raise
    else:
        scan.status = ShelfScan.Status.ERROR
        scan.llm_result = {"error": str(last_error)}
        scan.save()
        raise AppError("SCAN_AI_ERROR", "사진을 분석하지 못했어요. 다시 찍어 주세요", 502)

    scan.status = status
    scan.llm_result = {"raw": raw, "model": model, "items": result}
    scan.save()
    return scan


def scan_items(scan: ShelfScan) -> list[dict]:
    return (scan.llm_result or {}).get("items", [])


@transaction.atomic
def confirm_scan(scan: ShelfScan, target_date: date, items: list[dict]) -> None:
    """사장님이 고친 수량 확정 → records.update_left_qty 호출"""
    if scan.status == ShelfScan.Status.CONFIRMED:
        raise AppError("SCAN_ALREADY_CONFIRMED", "이미 확정한 사진이에요")
    if scan.status != ShelfScan.Status.OK:
        raise AppError("SCAN_NOT_CONFIRMABLE", "인식에 성공한 사진만 확정할 수 있어요")

    valid_ids = set(Item.objects.filter(store=scan.store).values_list("id", flat=True))
    quantities = {}
    for row in items:
        if row["item_id"] not in valid_ids:
            raise AppError("ITEM_NOT_FOUND", "품목을 찾을 수 없어요", 404)
        quantities[row["item_id"]] = row["quantity"]

    update_left_qty(scan.store_id, target_date, quantities)
    scan.status = ShelfScan.Status.CONFIRMED
    scan.confirmed_result = {"date": target_date.isoformat(),
                             "items": [{"item_id": k, "quantity": v} for k, v in quantities.items()]}
    scan.save()

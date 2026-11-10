from datetime import date, timedelta

from records.services import get_records


def build_dashboard(store_id: int, week_start: date) -> dict:
    """폐기 수량, 생산 vs 판매 집계 (week_start ~ +6일)"""
    records = get_records(store_id, week_start, week_start + timedelta(days=6))
    # TODO(B): 집계
    return {"week": week_start.isoformat(), "waste_qty": 0, "daily": []}

from pathlib import Path

PROMPT_PATH = Path(__file__).parent / "prompts" / "shelf_scan.txt"


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def create_scan(store, image_file):
    """업로드 → LLM 호출 → 응답 검증·재시도 → ShelfScan 저장"""
    raise NotImplementedError  # TODO(B)


def confirm_scan(scan, date, items: list[dict]) -> None:
    """확정 → records.services.update_left_qty 호출"""
    raise NotImplementedError  # TODO(B)

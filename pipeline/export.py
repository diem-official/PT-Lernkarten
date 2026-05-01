import json
from pathlib import Path


def build_entry(
    clean_filename: str,
    labels: list,
    *,
    category: str,
    subcategory: str,
    view: str,
) -> dict:
    return {
        "filename": clean_filename,
        "category": category,
        "subcategory": subcategory,
        "view": view,
        "labels": labels,
    }


def save_data_json(entries: list, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

#!/usr/bin/env python3
"""
Usage: python process.py <input_dir> [--output-web <web_dir>]

Processes all Kategorie-Unterkategorie-Ansicht.{jpg,png,...} files.

Pass 1 – OCR block extraction (PaddleOCR holds the GPU).
Pass 2 – VLM semantic grouping + union-box inpaint (Qwen holds the GPU).
"""
import argparse
import json
import logging
import re
import sys
from pathlib import Path
from PIL import Image

from vlm_classify import detect_labels, unload_model
from ocr import extract_labels, unload_engine, _union_box
from inpaint import draw_boxes, mask_text
from export import build_entry, save_data_json

log = logging.getLogger("process")

SUPPORTED = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
NAME_RE = re.compile(r'^[^-]+-[^-]+-[^-]+\.\w+$')
DEFAULT_WEB = Path(__file__).parent.parent / 'web'
DEFAULT_INPUT = Path(__file__).parent.parent / 'Input'

BOX_PADDING = 8


def _parse_stem(stem: str) -> tuple[str, str, str]:
    """Split 'Category-Subcategory-View' filename stem into three metadata parts."""
    parts = stem.split('-', 2)
    return parts[0], parts[1], parts[2]


def _write_report(entries: list, path: Path) -> None:
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    logging.basicConfig(level=logging.INFO, format='%(name)s %(levelname)s %(message)s')
    parser = argparse.ArgumentParser(description="Anatomy flashcard pipeline")
    parser.add_argument('input_dir', type=Path, nargs='?', default=DEFAULT_INPUT,
                        help=f"Directory with source images (default: {DEFAULT_INPUT})")
    parser.add_argument('--output-web', type=Path, default=DEFAULT_WEB,
                        help="Path to web/ directory (default: ../web)")
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        print(f"Error: {args.input_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    images_dir = args.output_web / 'data' / 'images'
    images_dir.mkdir(parents=True, exist_ok=True)

    all_files = sorted(p for p in args.input_dir.iterdir()
                       if p.suffix.lower() in SUPPORTED)

    if not all_files:
        print("No supported image files found.")
        sys.exit(0)

    output_dir = Path(__file__).parent.parent / 'Output'
    output_dir.mkdir(parents=True, exist_ok=True)

    valid_files = []
    for path in all_files:
        if NAME_RE.match(path.name):
            valid_files.append(path)
        else:
            print(f"  SKIP {path.name} – does not match Kategorie-Unterkategorie-Ansicht.ext")

    # ── Pass 1: OCR block extraction ─────────────────────────────────────────
    print(f"\n=== Pass 1: OCR block extraction ({len(valid_files)} images) ===")
    ocr_results: dict[Path, list] = {}
    marked_images: dict[Path, Image.Image] = {}

    for path in valid_files:
        print(f"[OCR] {path.name} ...")
        blocks = extract_labels(str(path))
        if blocks:
            print(f"  → {len(blocks)} block(s) extracted")
            with Image.open(path) as img:
                rgb = img.convert('RGB')
            marked = draw_boxes(rgb, blocks)
            marked.save(output_dir / f"{path.stem}-marked.jpg", 'JPEG', quality=95)
            marked_images[path] = marked
            ocr_results[path] = blocks
        else:
            print(f"  → No OCR blocks found, skipping")

    unload_engine()

    # ── Pass 2: VLM grouping + union-box + inpaint ───────────────────────────
    print(f"\n=== Pass 2: VLM grouping + inpaint ({len(ocr_results)} images) ===")
    qm_entries: list[dict] = []
    entries = []

    for path in valid_files:
        if path not in ocr_results:
            continue
        print(f"[VLM] {path.name} ...")
        img_w, img_h = marked_images[path].size
        ocr_blocks = ocr_results[path]

        # Parse metadata from filename (format: Category-Subcategory-View.ext)
        category, subcategory, view = _parse_stem(path.stem)

        vlm_result = detect_labels(marked_images[path], ocr_blocks)

        vlm_failed = bool(vlm_result.get("error", False))
        invalid_ids = set(vlm_result["invalid_ocr_ids"])

        if vlm_result["missing_words_detected"]:
            log.warning(
                "VLM reports missing labels in %s — some anatomical terms may lack red boxes; review output manually",
                path.name,
            )
        if invalid_ids:
            log.warning(
                "Removing %d invalid OCR block(s) flagged by VLM: ids=%s",
                len(invalid_ids),
                sorted(invalid_ids),
            )

        valid_blocks = [b for b in ocr_blocks if b["id"] not in invalid_ids]
        groupings = vlm_result["groupings"]

        # Build labels: anchor = left-centre of the first OCR block; mask_box = union of all blocks
        block_by_id = {b["id"]: b for b in valid_blocks}
        labels = []
        for g in groupings:
            blocks = [block_by_id[i] for i in g["ocr_ids"] if i in block_by_id]
            if not blocks:
                log.warning("No valid OCR blocks for term '%s' (ids=%s)", g["term"], g["ocr_ids"])
                continue
            first = blocks[0]
            anchor_x = first["x"]
            anchor_y = first["y"] + first["h"] / 2
            mask_box = _union_box(blocks, padding=BOX_PADDING, img_w=img_w, img_h=img_h)
            labels.append({
                "text": g["term"],
                "anchor_x": anchor_x,
                "anchor_y": anchor_y,
                "mask_box": mask_box,
            })

        qm_entries.append({
            "image": path.stem,
            "ocr_block_count": len(ocr_blocks),
            "missing_words_detected": vlm_result["missing_words_detected"],
            "invalid_ocr_ids": sorted(invalid_ids),
            "invalid_ocr_texts": [b["text"] for b in ocr_blocks if b["id"] in invalid_ids],
            "valid_block_count": len(ocr_blocks) - len(invalid_ids),
            "groupings_count": len(labels),
            "vlm_failed": vlm_failed,
        })

        if not labels:
            print(f"  → No valid labels after filtering, skipping")
            continue

        # Pass 3: Inpainting
        print(f"  → {len(labels)} label(s) grouped, {len(valid_blocks)} valid block(s) to mask")
        image = Image.open(path).convert('RGB')
        clean = mask_text(image, valid_blocks)
        clean_name = f"{path.stem}-clean.jpg"
        clean.save(images_dir / clean_name, 'JPEG', quality=95)
        print(f"  Saved → {clean_name}")
        entries.append(build_entry(
            clean_name,
            labels,
            category=category,
            subcategory=subcategory,
            view=view,
        ))

    _write_report(qm_entries, output_dir / 'report.json')
    unload_model()

    json_out = args.output_web / 'data' / 'data.json'
    save_data_json(entries, json_out)

    print(f"\nDone. {len(entries)}/{len(all_files)} images processed.")
    print(f"data.json → {json_out}")


if __name__ == '__main__':
    main()

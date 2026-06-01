#!/usr/bin/env python3
"""
Usage: python process.py <input_dir> [--output-web <web_dir>]

Processes all Kategorie-Unterkategorie-Ansicht.{jpg,png,...} files.

Pass 1 – OCR block extraction.
Pass 2 – Layout-based term extraction + label building + inpaint.
"""
import argparse
import json
import logging
import re
import shutil
import sys
from pathlib import Path
from PIL import Image, ImageOps

import cv2
from semantic_classify import detect_labels, unload_model
from ocr import extract_labels, unload_engine, _union_box
from inpaint import draw_boxes, mask_text
from export import build_entry, save_data_json

log = logging.getLogger("process")

SUPPORTED = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
NAME_RE = re.compile(r'^[^-]+-[^-]+-[^-]+\.\w+$')
DEFAULT_WEB = Path(__file__).parent.parent / 'web'
DEFAULT_INPUT = Path(__file__).parent.parent / 'Input'
RAW_IMAGES_DIR = Path('/home/diem/PT Lernkarten/Bilder')
MAX_OCR_DIM = 2500

BOX_PADDING = 8


def _parse_stem(stem: str) -> tuple[str, str, str]:
    """Split 'Category-Subcategory-View' filename stem into three metadata parts."""
    parts = stem.split('-', 2)
    return parts[0], parts[1], parts[2]


def _preprocess_images(src_dir: Path, dst_dir: Path) -> None:
    """Resize images exceeding MAX_OCR_DIM while maintaining aspect ratio."""
    if not src_dir.is_dir():
        return

    dst_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n=== Preprocessing: {src_dir} -> {dst_dir} ===")
    for path in src_dir.iterdir():
        if path.suffix.lower() not in SUPPORTED:
            continue

        target = dst_dir / path.name
        with Image.open(path) as img:
            # Apply EXIF orientation (rotation) correctly before checking dimensions
            img = ImageOps.exif_transpose(img)
            w, h = img.size
            if max(w, h) > MAX_OCR_DIM:
                scale = MAX_OCR_DIM / max(w, h)
                new_size = (int(w * scale), int(h * scale))
                # Use high-quality resampling (LANCZOS)
                resampling = getattr(Image, 'Resampling', Image).LANCZOS
                img.resize(new_size, resampling).save(target, quality=95)
                print(f"  Resized {path.name} to {new_size}")
            else:
                # If no scaling needed, save the EXIF-corrected image to the target
                img.save(target, quality=95)
                print(f"  Copied {path.name} (no scaling needed, EXIF applied)")


def _filter_noise_blocks(blocks: list[dict]) -> list[dict]:
    """Drop single-char and non-alphabetic OCR blocks."""
    def is_noise(text: str) -> bool:
        return len(text) <= 1 or not any(c.isalpha() for c in text)
    return [b for b in blocks if not is_noise(b["text"])]


def _write_report(entries: list, path: Path) -> None:
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')


def _build_labels_from_terms(
    terms: list[dict],
    ocr_blocks: list[dict],
    img_w: int,
    img_h: int,
) -> tuple[list[dict], set[int], list[str]]:
    """Look up OCR blocks by term IDs and build label dicts.

    Returns (labels, used_ids, orphaned_term_names).
    """
    block_by_id = {b["id"]: b for b in ocr_blocks}
    labels: list[dict] = []
    used_ids: set[int] = set()
    orphaned: list[str] = []

    for term in terms:
        matched = [block_by_id[i] for i in term["ids"] if i in block_by_id]
        if not matched:
            orphaned.append(term["name"])
            continue
        sorted_blocks = sorted(matched, key=lambda b: b["y"])
        first = sorted_blocks[0]
        labels.append({
            "text": term["name"],
            "anchor_x": first["x"],
            "anchor_y": first["y"] + first["h"] / 2,
            "mask_box": _union_box(matched, BOX_PADDING, img_w, img_h),
        })
        used_ids.update(term["ids"])

    return labels, used_ids, orphaned


def main():
    logging.basicConfig(level=logging.INFO, format='%(name)s %(levelname)s %(message)s')
    parser = argparse.ArgumentParser(description="Anatomy flashcard pipeline")
    parser.add_argument('input_dir', type=Path, nargs='?', default=DEFAULT_INPUT,
                        help=f"Directory with source images (default: {DEFAULT_INPUT})")
    parser.add_argument('--output-web', type=Path, default=DEFAULT_WEB,
                        help="Path to web/ directory (default: ../web)")
    args = parser.parse_args()

    json_out = args.output_web / 'data' / 'data.json'
    existing_entries: list[dict] = []
    processed_stems: set[str] = set()
    if json_out.exists():
        existing_entries = json.loads(json_out.read_text(encoding='utf-8'))
        processed_stems = {Path(e['og_filename']).stem for e in existing_entries}
        print(f"Bestehende data.json geladen: {len(existing_entries)} Einträge.")

    _preprocess_images(RAW_IMAGES_DIR, args.input_dir)

    if not args.input_dir.is_dir():
        print(f"Error: {args.input_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    images_dir = args.output_web / 'data' / 'images'
    images_dir.mkdir(parents=True, exist_ok=True)
    og_images_dir = args.output_web / 'data' / 'og-images'
    og_images_dir.mkdir(parents=True, exist_ok=True)

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

    already_done = [p for p in valid_files if p.stem in processed_stems]
    for p in already_done:
        print(f"  SKIP {p.name} – bereits in data.json")
    valid_files = [p for p in valid_files if p.stem not in processed_stems]

    if not valid_files:
        print("Keine neuen Bilder zu verarbeiten.")
        return

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
            marked = draw_boxes(rgb, _filter_noise_blocks(blocks))
            marked.save(output_dir / f"{path.stem}-marked.jpg", 'JPEG', quality=95)
            marked_images[path] = marked
            ocr_results[path] = blocks
        else:
            print(f"  → No OCR blocks found, skipping")

    unload_engine()

    # ── Pass 2: Layout-based term extraction + label building + inpaint ─────
    print(f"\n=== Pass 2: Term extraction ({len(ocr_results)} images) ===")
    qm_entries: list[dict] = []
    entries = []

    for path in valid_files:
        if path not in ocr_results:
            continue
        print(f"[classify] {path.name} ...")
        img_w, img_h = marked_images[path].size
        raw_blocks = ocr_results[path]
        ocr_blocks = _filter_noise_blocks(raw_blocks)
        noise_filtered = len(raw_blocks) - len(ocr_blocks)
        if noise_filtered:
            log.info(
                "Pre-filtered %d noise OCR block(s) in %s: %s",
                noise_filtered,
                path.name,
                [b["text"] for b in raw_blocks if b not in ocr_blocks],
            )

        category, subcategory, view = _parse_stem(path.stem)

        img_bgr = cv2.imread(str(path))
        classify_result = detect_labels(ocr_blocks, image=img_bgr)
        terms: list[dict] = classify_result.get("terms", [])

        labels, used_ids, orphaned_terms = _build_labels_from_terms(
            terms, ocr_blocks, img_w, img_h
        )

        orphaned_ocr_blocks = [b["text"] for b in ocr_blocks if b["id"] not in used_ids]

        if orphaned_terms:
            log.warning(
                "%s: %d orphaned term(s) — manual review required: %s",
                path.name, len(orphaned_terms), orphaned_terms,
            )
        if orphaned_ocr_blocks:
            log.warning(
                "%s: %d unmatched OCR block(s) — manual review required: %s",
                path.name, len(orphaned_ocr_blocks), orphaned_ocr_blocks,
            )

        qm_entries.append({
            "image": path.stem,
            "ocr_block_count": len(raw_blocks),
            "noise_filtered_count": noise_filtered,
            "term_count": len(terms),
            "matched_labels_count": len(labels),
            "orphaned_terms": orphaned_terms,
            "orphaned_ocr_blocks": orphaned_ocr_blocks,
        })

        if not labels:
            print(f"  → No valid labels, skipping")
            continue

        # ── Pass 3: Inpainting ────────────────────────────────────────────────
        print(f"  → {len(labels)} label(s) accepted, {len(ocr_blocks)} block(s) to mask")
        image = Image.open(path).convert('RGB')
        clean = mask_text(image, ocr_blocks)
        clean_name = f"{path.stem}-clean.jpg"
        clean.save(images_dir / clean_name, 'JPEG', quality=95)
        og_name = path.name
        shutil.copy2(path, og_images_dir / og_name)
        print(f"  Saved → {clean_name}")
        entries.append(build_entry(
            clean_name,
            og_name,
            labels,
            category=category,
            subcategory=subcategory,
            view=view,
        ))

    _write_report(qm_entries, output_dir / 'report.json')
    unload_model()

    save_data_json(existing_entries + entries, json_out)

    print(f"\nDone. {len(entries)}/{len(all_files)} images processed.")
    print(f"data.json → {json_out}")


if __name__ == '__main__':
    main()

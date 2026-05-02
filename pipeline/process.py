#!/usr/bin/env python3
"""
Usage: python process.py <input_dir> [--output-web <web_dir>]

Processes all Kategorie-Unterkategorie-Ansicht.{jpg,png,...} files.

Pass 1 – OCR block extraction (PaddleOCR holds the GPU).
Pass 2 – VLM term extraction + string-matching + union-box + inpaint (Qwen holds the GPU).
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


def _filter_noise_blocks(blocks: list[dict]) -> list[dict]:
    """Drop single-char and non-alphabetic OCR blocks before VLM processing."""
    def is_noise(text: str) -> bool:
        return len(text) <= 1 or not any(c.isalpha() for c in text)
    return [b for b in blocks if not is_noise(b["text"])]


def _write_report(entries: list, path: Path) -> None:
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')


def _word_tokens(text: str) -> list[str]:
    """Lowercase alphabetic tokens from text (strips punctuation, handles umlauts)."""
    return re.findall(r'[a-zA-ZäöüÄÖÜß]+', text.lower())


def _build_word_freq(pool: list[dict]) -> dict[str, int]:
    """Count how many pool blocks contain each lowercase word token."""
    freq: dict[str, int] = {}
    for block in pool:
        for w in set(_word_tokens(block["text"])):
            freq[w] = freq.get(w, 0) + 1
    return freq


def _find_block_containing_word(word: str, pool: list[dict]) -> dict | None:
    """Return first pool block whose text contains the word as a whole token."""
    target = word.lower()
    for block in pool:
        if target in _word_tokens(block["text"]):
            return block
    return None


def _find_block_near_anchor(word: str, anchor: dict, pool: list[dict]) -> dict | None:
    """Return the closest pool block within spatial tolerance that contains the word."""
    max_dist = anchor["h"] * 1.5
    anchor_cx = anchor["x"] + anchor["w"] / 2
    anchor_cy = anchor["y"] + anchor["h"] / 2
    target = word.lower()

    best_dist = float("inf")
    best_block: dict | None = None
    for block in pool:
        if target not in _word_tokens(block["text"]):
            continue
        cx = block["x"] + block["w"] / 2
        cy = block["y"] + block["h"] / 2
        if abs(cx - anchor_cx) <= max_dist and abs(cy - anchor_cy) <= max_dist:
            dist = abs(cx - anchor_cx) + abs(cy - anchor_cy)
            if dist < best_dist:
                best_dist = dist
                best_block = block
    return best_block


def _match_vlm_term(
    term: str,
    pool: list[dict],
    img_w: int,
    img_h: int,
) -> tuple[dict | None, list[dict], list[str]]:
    """
    Match a VLM term against OCR pool.
    Returns (union_box | None, matched_blocks, unmatched_words).
    Removes matched blocks from pool in-place.

    unmatched_words is empty on full match, non-empty on partial match.
    union_box is None when no blocks were found at all.
    """
    term_s = term.strip()

    # Phase 1: direct full-string match
    for block in pool:
        if block["text"].strip().lower() == term_s.lower():
            pool[:] = [b for b in pool if b["id"] != block["id"]]
            return _union_box([block], BOX_PADDING, img_w, img_h), [block], []

    # Phase 2+3: anchor search + spatial proximity (multi-word terms only)
    words = term_s.split()
    if len(words) < 2:
        return None, [], [term_s]

    freq = _build_word_freq(pool)

    # Phase 2: select anchor as rarest word present in pool
    anchor_word: str | None = None
    anchor_block: dict | None = None
    rarest_count = float("inf")
    for w in words:
        count = freq.get(w.lower(), 0)
        if 0 < count < rarest_count:
            blk = _find_block_containing_word(w, pool)
            if blk is not None:
                rarest_count = count
                anchor_word = w
                anchor_block = blk

    if anchor_block is None:
        return None, [], words

    matched_blocks = [anchor_block]
    pool[:] = [b for b in pool if b["id"] != anchor_block["id"]]

    # Remaining words: skip first occurrence of anchor word
    remaining: list[str] = []
    skipped = False
    for w in words:
        if not skipped and w.lower() == anchor_word.lower():
            skipped = True
            continue
        remaining.append(w)

    # Phase 3: spatial proximity search for remaining words
    unmatched: list[str] = []
    for w in remaining:
        blk = _find_block_near_anchor(w, anchor_block, pool)
        if blk is not None:
            matched_blocks.append(blk)
            pool[:] = [b for b in pool if b["id"] != blk["id"]]
        else:
            unmatched.append(w)
            log.debug(
                "Phase 3: '%s' not found near anchor '%s' for term '%s'",
                w, anchor_word, term,
            )

    return _union_box(matched_blocks, BOX_PADDING, img_w, img_h), matched_blocks, unmatched


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

    # ── Pass 2: VLM term extraction + string matching + inpaint ─────────────
    print(f"\n=== Pass 2: VLM term extraction + string matching ({len(ocr_results)} images) ===")
    qm_entries: list[dict] = []
    entries = []

    for path in valid_files:
        if path not in ocr_results:
            continue
        print(f"[VLM] {path.name} ...")
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

        vlm_result = detect_labels(marked_images[path], ocr_blocks)
        vlm_failed = bool(vlm_result.get("error", False))
        vlm_terms: list[str] = vlm_result.get("terms", [])

        # ── String-matching pipeline ──────────────────────────────────────────
        pool: list[dict] = list(ocr_blocks)
        labels: list[dict] = []
        orphaned_vlm_terms: list[str] = []

        for term in vlm_terms:
            box, matched_blocks, unmatched_words = _match_vlm_term(
                term, pool, img_w, img_h
            )

            if box is None:
                orphaned_vlm_terms.append(term)
                log.warning("No OCR match for VLM term '%s' in %s", term, path.name)
                continue

            if unmatched_words:
                orphaned_vlm_terms.append(term)
                log.warning(
                    "Partial match for '%s' in %s — missing words: %s",
                    term, path.name, unmatched_words,
                )
                continue

            first = matched_blocks[0]
            labels.append({
                "text": term,
                "anchor_x": first["x"],
                "anchor_y": first["y"] + first["h"] / 2,
                "mask_box": box,
            })

        # ── Orphan check ──────────────────────────────────────────────────────
        orphaned_ocr_blocks = [b["text"] for b in pool]

        if orphaned_vlm_terms:
            log.warning(
                "%s: %d orphaned VLM term(s) — manual review required: %s",
                path.name, len(orphaned_vlm_terms), orphaned_vlm_terms,
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
            "vlm_term_count": len(vlm_terms),
            "matched_labels_count": len(labels),
            "orphaned_vlm_terms": orphaned_vlm_terms,
            "orphaned_ocr_blocks": orphaned_ocr_blocks,
            "vlm_failed": vlm_failed,
        })

        if not labels:
            print(f"  → No valid labels after matching, skipping")
            continue

        # ── Pass 3: Inpainting ────────────────────────────────────────────────
        print(f"  → {len(labels)} label(s) matched, {len(ocr_blocks)} block(s) to mask")
        image = Image.open(path).convert('RGB')
        clean = mask_text(image, ocr_blocks)
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

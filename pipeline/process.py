#!/usr/bin/env python3
"""
Usage: python process.py <input_dir> [--output-web <web_dir>]

Processes all Kategorie-Unterkategorie-Ansicht.{jpg,png,...} files.
Writes clean images to <web_dir>/data/images/ and data.json to <web_dir>/data/.
"""
import argparse
import re
import sys
from pathlib import Path
from PIL import Image

from ocr import extract_labels
from inpaint import remove_text
from export import build_entry, save_data_json

SUPPORTED = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
NAME_RE = re.compile(r'^[^-]+-[^-]+-[^-]+\.\w+$')
DEFAULT_WEB = Path(__file__).parent.parent / 'web'
DEFAULT_INPUT = Path(__file__).parent.parent / 'Input'


def process_image(image_path: Path, images_dir: Path) -> dict | None:
    if not NAME_RE.match(image_path.name):
        print(f"  SKIP {image_path.name} – does not match Kategorie-Unterkategorie-Ansicht.ext")
        return None

    print(f"Processing {image_path.name} ...")
    labels = extract_labels(str(image_path))

    if not labels:
        print(f"  No text detected – skipping")
        return None

    print(f"  Found {len(labels)} label(s)")
    image = Image.open(image_path).convert('RGB')
    clean = remove_text(image, labels)

    clean_name = f"{image_path.stem}-clean.jpg"
    clean.save(images_dir / clean_name, 'JPEG', quality=95)
    print(f"  Saved → {clean_name}")

    return build_entry(clean_name, labels)


def main():
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

    entries = []
    image_files = sorted(p for p in args.input_dir.iterdir()
                         if p.suffix.lower() in SUPPORTED)

    if not image_files:
        print("No supported image files found.")
        sys.exit(0)

    for path in image_files:
        entry = process_image(path, images_dir)
        if entry:
            entries.append(entry)

    json_out = args.output_web / 'data' / 'data.json'
    save_data_json(entries, json_out)

    print(f"\nDone. {len(entries)}/{len(image_files)} images processed.")
    print(f"data.json → {json_out}")


if __name__ == '__main__':
    main()

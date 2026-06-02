#!/usr/bin/env python3
"""
Einmalige Migration: 3-teilige → 4-teilige Dateinamen (Fach-Präfix).

Schritte:
  1. Input/-Dateien umbenennen (Präfix „Anatomie 1-")
  2. Tabellen/-Dateien umbenennen
  3. web/data/og-images/-Dateien umbenennen
  4. web/data/data.json aktualisieren: subject hinzufügen, og_filename updaten
  5. web/data/text-data.json aktualisieren: subject hinzufügen

WICHTIG: web/data/images/ (Clean-Images) wird NICHT angefasst.
         Die filename-Felder in data.json bleiben unverändert.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
INPUT_DIR   = ROOT / 'Input'
TABELLEN_DIR = ROOT / 'Tabellen'
OG_IMAGES_DIR = ROOT / 'web' / 'data' / 'og-images'
DATA_JSON    = ROOT / 'web' / 'data' / 'data.json'
TEXT_JSON    = ROOT / 'web' / 'data' / 'text-data.json'
DEFAULT_FACH = 'Anatomie 1'
PREFIX       = DEFAULT_FACH + '-'

SUPPORTED_IMG = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
SUPPORTED_TBL = {'.xlsx', '.csv'}


def _needs_prefix(name: str) -> bool:
    return not name.startswith(PREFIX)


def _rename_files(directory: Path, extensions: set) -> int:
    count = 0
    if not directory.is_dir():
        print(f"  SKIP {directory} — nicht gefunden")
        return 0
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in extensions:
            continue
        if _needs_prefix(path.name):
            new_path = path.parent / (PREFIX + path.name)
            path.rename(new_path)
            print(f"  {path.name}  →  {new_path.name}")
            count += 1
        else:
            print(f"  SKIP (bereits migriert): {path.name}")
    return count


def _migrate_data_json(path: Path) -> None:
    if not path.exists():
        print(f"  SKIP {path} — nicht gefunden")
        return
    with open(path, encoding='utf-8') as f:
        entries = json.load(f)
    changed = 0
    for entry in entries:
        if 'subject' not in entry:
            entry['subject'] = DEFAULT_FACH
            changed += 1
        og = entry.get('og_filename', '')
        if og and _needs_prefix(og):
            entry['og_filename'] = PREFIX + og
            changed += 1
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"  {path.name}: {changed} Felder aktualisiert ({len(entries)} Einträge)")


def _migrate_text_json(path: Path) -> None:
    if not path.exists():
        print(f"  SKIP {path} — nicht gefunden")
        return
    with open(path, encoding='utf-8') as f:
        entries = json.load(f)
    changed = 0
    for entry in entries:
        if 'subject' not in entry:
            entry['subject'] = DEFAULT_FACH
            changed += 1
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"  {path.name}: {changed} Felder aktualisiert ({len(entries)} Einträge)")


def main():
    print(f"\n=== Migration zu Fach-Hierarchie (Fach: '{DEFAULT_FACH}') ===\n")

    print("Schritt 1: Input/-Dateien umbenennen")
    n = _rename_files(INPUT_DIR, SUPPORTED_IMG)
    print(f"  → {n} Dateien umbenannt\n")

    print("Schritt 2: Tabellen/-Dateien umbenennen")
    n = _rename_files(TABELLEN_DIR, SUPPORTED_TBL)
    print(f"  → {n} Dateien umbenannt\n")

    print("Schritt 3: og-images/-Dateien umbenennen")
    n = _rename_files(OG_IMAGES_DIR, SUPPORTED_IMG)
    print(f"  → {n} Dateien umbenannt\n")

    print("Schritt 4: data.json aktualisieren")
    _migrate_data_json(DATA_JSON)
    print()

    print("Schritt 5: text-data.json aktualisieren")
    _migrate_text_json(TEXT_JSON)
    print()

    print("=== Migration abgeschlossen ===")
    print("HINWEIS: web/data/images/ wurde NICHT angefasst (Clean-Images bleiben unverändert).")


if __name__ == '__main__':
    main()

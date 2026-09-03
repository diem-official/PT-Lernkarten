#!/usr/bin/env python3
"""Convert an Excel or CSV quiz table into web/data/text-data.json.

File naming convention (same as images):
    Fach-Kategorie-Unterkategorie-Ansicht.xlsx
    Fach-Kategorie-Unterkategorie-Ansicht.csv

Table format:
    Row 1 : column headers  (first column = subject label, rest = answer categories)
    Row 2+: data rows       (first cell = question, other cells = answers separated by ";")

Optional: if cell A1 is "BILD", cell B1 holds an image filename and the header
row starts at row 2; the entry then carries an {"og", "clean"} image reference.
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path


def _parse_stem(stem):
    """Split 'Fach-Kategorie-Unterkategorie-Ansicht' into a dict (max 3 splits)."""
    parts = stem.split('-', 3)
    if len(parts) < 4:
        return None
    return {
        'subject':     parts[0].strip(),
        'category':    parts[1].strip(),
        'subcategory': parts[2].strip(),
        'view':        parts[3].strip(),
    }


def _split_answers(cell_value):
    """Split a cell value by ';', strip whitespace, drop empty strings."""
    if cell_value is None:
        return []
    return [a.strip() for a in str(cell_value).split(';') if a.strip()]


def _extract_image_meta(all_rows):
    """Detect and extract optional BILD meta-row from the top of all_rows.

    Returns (image_meta, remaining_rows).
    image_meta is None if no BILD row, else {"og": ..., "clean": ...}.
    """
    if not all_rows:
        return None, all_rows

    first_cell = all_rows[0][0]
    if first_cell is None or str(first_cell).strip().lower() != 'bild':
        return None, all_rows

    remaining = all_rows[1:]
    if not remaining:
        sys.exit('Fehler: BILD-Zeile vorhanden, aber keine Header-Zeile gefunden.')

    b1 = all_rows[0][1] if len(all_rows[0]) > 1 else None
    b1_str = str(b1).strip() if b1 is not None else ''
    if not b1_str or '.' not in b1_str:
        sys.exit(
            'Fehler: BILD-Zeile muss in Zelle B1 einen gültigen Dateinamen '
            '(mit Dateiendung, z. B. Anatomie 1-Bänder-Becken-Dorsal.png) enthalten.'
        )

    og_filename = b1_str
    clean_filename = Path(og_filename).stem + '-clean.jpg'
    return {'og': og_filename, 'clean': clean_filename}, remaining


def _read_excel(filepath):
    try:
        import openpyxl
    except ImportError:
        sys.exit(
            'openpyxl ist nicht installiert.\n'
            'Bitte installieren: pip install openpyxl'
        )
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active
    return list(ws.iter_rows(values_only=True))


def _read_csv(filepath):
    for delimiter in (';', ',', '\t'):
        with open(filepath, newline='', encoding='utf-8-sig') as f:
            sample = f.read(4096)
            if delimiter in sample:
                break
    with open(filepath, newline='', encoding='utf-8-sig') as f:
        return list(csv.reader(f, delimiter=delimiter))


def _build_entry(meta, headers, data_rows, image=None):
    columns = headers[1:]  # first column is the question/subject label
    rows = []
    for row in data_rows:
        if all(cell is None or str(cell).strip() == '' for cell in row):
            continue
        question = str(row[0]).strip() if row[0] is not None else ''
        if not question:
            continue
        answers = {}
        for i, col_name in enumerate(columns):
            col_idx = i + 1
            cell_val = row[col_idx] if col_idx < len(row) else None
            answers[col_name] = _split_answers(cell_val)
        rows.append({'question': question, 'answers': answers})

    entry = {
        'type':        'text',
        'subject':     meta['subject'],
        'category':    meta['category'],
        'subcategory': meta['subcategory'],
        'view':        meta['view'],
    }
    if image is not None:
        entry['image'] = image
    entry['columns'] = columns
    entry['rows'] = rows
    return entry


def main():
    parser = argparse.ArgumentParser(
        description='Excel/CSV → text-data.json für das Anatomie-Lernprogramm'
    )
    parser.add_argument('input', help='Eingabedatei (.xlsx oder .csv)')
    parser.add_argument(
        '--output', default=None,
        help='Pfad zur text-data.json (Standard: web/data/text-data.json)'
    )
    args = parser.parse_args()

    filepath = args.input
    if not os.path.isfile(filepath):
        sys.exit(f'Datei nicht gefunden: {filepath}')

    ext = os.path.splitext(filepath)[1].lower()
    if ext not in ('.xlsx', '.csv'):
        sys.exit(f'Nicht unterstütztes Format: {ext}  (nur .xlsx und .csv erlaubt)')

    stem = os.path.splitext(os.path.basename(filepath))[0]
    meta = _parse_stem(stem)
    if meta is None:
        sys.exit(
            f'Dateiname "{stem}" folgt nicht dem Format Fach-Kategorie-Unterkategorie-Ansicht\n'
            f'Beispiel: "Anatomie 1-Muskeln-Gesäß-Gluteus.xlsx"'
        )

    print(f'Verarbeite: {filepath}')
    if ext == '.xlsx':
        all_rows = _read_excel(filepath)
    else:
        all_rows = _read_csv(filepath)

    image_meta, remaining_rows = _extract_image_meta(all_rows)

    if not remaining_rows:
        sys.exit('Tabelle ist leer oder enthält nur die BILD-Zeile (keine Header-Zeile gefunden).')

    headers = [str(h).strip() if h is not None else '' for h in remaining_rows[0]]
    data_rows = remaining_rows[1:]

    if len(headers) < 2:
        sys.exit('Tabelle muss mindestens 2 Spalten haben (Frage + mindestens 1 Antwortkategorie)')

    entry = _build_entry(meta, headers, data_rows, image=image_meta)
    print(f'  {len(entry["rows"])} Fragen, {len(entry["columns"])} Antwortkategorien')
    if image_meta:
        print(f'  Bild: {image_meta["og"]} / {image_meta["clean"]}')

    if args.output:
        output_path = os.path.normpath(args.output)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.normpath(
            os.path.join(script_dir, '..', 'web', 'data', 'text-data.json')
        )

    existing = []
    if os.path.isfile(output_path):
        with open(output_path, encoding='utf-8') as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                pass

    # Replace existing entry with same key, otherwise append
    key = (entry['subject'], entry['category'], entry['subcategory'], entry['view'])
    replaced = False
    for i, ex in enumerate(existing):
        if (ex.get('subject'), ex.get('category'), ex.get('subcategory'), ex.get('view')) == key:
            existing[i] = entry
            replaced = True
            break
    if not replaced:
        existing.append(entry)

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    action = 'aktualisiert' if replaced else 'hinzugefügt'
    print(f'  {action}: {entry["category"]} > {entry["subcategory"]} > {entry["view"]}')
    print(f'  Gespeichert: {output_path}')


if __name__ == '__main__':
    main()

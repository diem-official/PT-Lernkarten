#!/usr/bin/env python3
"""Convert an Excel or CSV quiz table into web/data/text-data.json.

File naming convention (same as images):
    Kategorie-Unterkategorie-Ansicht.xlsx
    Kategorie-Unterkategorie-Ansicht.csv

Table format:
    Row 1 : column headers  (first column = subject label, rest = answer categories)
    Row 2+: data rows       (first cell = question, other cells = answers separated by ";")
"""

import argparse
import csv
import json
import os
import sys


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
    all_rows = list(ws.iter_rows(values_only=True))
    if not all_rows:
        return [], []
    headers = [str(h).strip() if h is not None else '' for h in all_rows[0]]
    return headers, all_rows[1:]


def _read_csv(filepath):
    # Auto-detect delimiter: try semicolon first, then comma
    for delimiter in (';', ',', '\t'):
        with open(filepath, newline='', encoding='utf-8-sig') as f:
            sample = f.read(4096)
            if delimiter in sample:
                break
    with open(filepath, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.reader(f, delimiter=delimiter))
    if not rows:
        return [], []
    headers = [h.strip() for h in rows[0]]
    return headers, rows[1:]


def _build_entry(meta, headers, data_rows):
    columns = headers[1:]  # first column is the question/subject label
    rows = []
    for row in data_rows:
        if all(cell is None or str(cell).strip() == '' for cell in row):
            continue  # skip blank rows
        question = str(row[0]).strip() if row[0] is not None else ''
        if not question:
            continue
        answers = {}
        for i, col_name in enumerate(columns):
            col_idx = i + 1
            cell_val = row[col_idx] if col_idx < len(row) else None
            answers[col_name] = _split_answers(cell_val)
        rows.append({'question': question, 'answers': answers})
    return {
        'type':        'text',
        'subject':     meta['subject'],
        'category':    meta['category'],
        'subcategory': meta['subcategory'],
        'view':        meta['view'],
        'columns':     columns,
        'rows':        rows,
    }


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
        headers, data_rows = _read_excel(filepath)
    else:
        headers, data_rows = _read_csv(filepath)

    if len(headers) < 2:
        sys.exit('Tabelle muss mindestens 2 Spalten haben (Frage + mindestens 1 Antwortkategorie)')

    entry = _build_entry(meta, headers, data_rows)
    print(f'  {len(entry["rows"])} Fragen, {len(entry["columns"])} Antwortkategorien')

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

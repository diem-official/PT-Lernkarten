# Text-Quiz Bild-Support + Image Naming Migration – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate clean image filenames to a uniform `<subject-stem>-clean.jpg` scheme, then add optional image display (above input fields) to table-based text quizzes via a `BILD` meta-row in Excel.

**Architecture:** Three independent layers – (1) a standalone migration script that renames files + updates data.json, (2) pipeline changes to `convert_text.py` that parse an optional BILD meta-row from Excel and embed image metadata in text-data.json, (3) frontend changes to quiz.js/app.js/style.css that render the image at the top of the text quiz wrapper.

**Tech Stack:** Python 3.12, pytest, openpyxl, vanilla JS (ES5), CSS

---

## File Map

| File | Role |
|------|------|
| `pipeline/migrate_images.py` | **New** – CLI script: renames images/, updates data.json |
| `pipeline/tests/test_migrate_images.py` | **New** – Unit tests for migration logic |
| `pipeline/convert_text.py` | **Modify** – read functions return all_rows; add `_extract_image_meta`; update `_build_entry` and `main` |
| `pipeline/tests/test_convert_text.py` | **New** – Unit tests for new convert_text functions |
| `web/js/quiz.js:158,219` | **Modify** – add `ogImgBase`/`imgBase` param; render image at top |
| `web/js/app.js:71,73` | **Modify** – pass `OG_IMG_BASE` / `IMG_BASE` to text quiz functions |
| `web/css/style.css:458` | **Modify** – add `.tq-quiz-image` class before mobile media query |

---

## Task 1: Migrations-Script

**Files:**
- Create: `pipeline/migrate_images.py`
- Create: `pipeline/tests/test_migrate_images.py`

- [ ] **Step 1.1: Failing tests schreiben**

Erstelle `pipeline/tests/test_migrate_images.py`:

```python
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from pathlib import Path
import migrate_images


def _make_data_json(tmp_path, entries):
    p = tmp_path / 'data' / 'data.json'
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
    return p


def _make_image(tmp_path, name):
    p = tmp_path / 'data' / 'images' / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b'fake')
    return p


# ── _derive_clean_name ────────────────────────────────────────────────────────

def test_derive_clean_name_strips_nothing_adds_suffix():
    assert migrate_images._derive_clean_name('Anatomie 1-Bänder-Becken-Dorsal.png') == \
        'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'


def test_derive_clean_name_preserves_special_chars():
    assert migrate_images._derive_clean_name('Anatomie 1-Knochen-Becken-Ventral (Mann).png') == \
        'Anatomie 1-Knochen-Becken-Ventral (Mann)-clean.jpg'


# ── migrate: dry-run ──────────────────────────────────────────────────────────

def test_dryrun_does_not_rename_files(tmp_path):
    entries = [{'og_filename': 'Anatomie 1-Bänder-Becken-Dorsal.png',
                'filename': 'Bänder-Becken-Dorsal-clean.jpg'}]
    _make_data_json(tmp_path, entries)
    old_img = _make_image(tmp_path, 'Bänder-Becken-Dorsal-clean.jpg')

    migrate_images.migrate(tmp_path, apply=False)

    assert old_img.exists()
    new_img = tmp_path / 'data' / 'images' / 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'
    assert not new_img.exists()


def test_dryrun_does_not_modify_data_json(tmp_path):
    entries = [{'og_filename': 'Anatomie 1-Bänder-Becken-Dorsal.png',
                'filename': 'Bänder-Becken-Dorsal-clean.jpg'}]
    data_json = _make_data_json(tmp_path, entries)
    original = data_json.read_text(encoding='utf-8')
    _make_image(tmp_path, 'Bänder-Becken-Dorsal-clean.jpg')

    migrate_images.migrate(tmp_path, apply=False)

    assert data_json.read_text(encoding='utf-8') == original


# ── migrate: apply ────────────────────────────────────────────────────────────

def test_apply_renames_file(tmp_path):
    entries = [{'og_filename': 'Anatomie 1-Bänder-Becken-Dorsal.png',
                'filename': 'Bänder-Becken-Dorsal-clean.jpg'}]
    _make_data_json(tmp_path, entries)
    old_img = _make_image(tmp_path, 'Bänder-Becken-Dorsal-clean.jpg')

    migrate_images.migrate(tmp_path, apply=True)

    assert not old_img.exists()
    new_img = tmp_path / 'data' / 'images' / 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'
    assert new_img.exists()


def test_apply_updates_data_json(tmp_path):
    entries = [{'og_filename': 'Anatomie 1-Bänder-Becken-Dorsal.png',
                'filename': 'Bänder-Becken-Dorsal-clean.jpg'}]
    data_json = _make_data_json(tmp_path, entries)
    _make_image(tmp_path, 'Bänder-Becken-Dorsal-clean.jpg')

    migrate_images.migrate(tmp_path, apply=True)

    updated = json.loads(data_json.read_text(encoding='utf-8'))
    assert updated[0]['filename'] == 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'


def test_apply_creates_backup(tmp_path):
    entries = [{'og_filename': 'Anatomie 1-Bänder-Becken-Dorsal.png',
                'filename': 'Bänder-Becken-Dorsal-clean.jpg'}]
    _make_data_json(tmp_path, entries)
    _make_image(tmp_path, 'Bänder-Becken-Dorsal-clean.jpg')

    migrate_images.migrate(tmp_path, apply=True)

    assert (tmp_path / 'data' / 'data.json.bak').exists()


def test_apply_skips_already_correct(tmp_path):
    entries = [{'og_filename': 'Anatomie 1-Bänder-Becken-Dorsal.png',
                'filename': 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'}]
    data_json = _make_data_json(tmp_path, entries)
    img = _make_image(tmp_path, 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg')
    original = data_json.read_text(encoding='utf-8')

    migrate_images.migrate(tmp_path, apply=True)

    assert data_json.read_text(encoding='utf-8') == original
    assert img.exists()


def test_apply_target_exists_updates_json_without_rename(tmp_path):
    entries = [{'og_filename': 'Anatomie 1-Bänder-Becken-Dorsal.png',
                'filename': 'Bänder-Becken-Dorsal-clean.jpg'}]
    data_json = _make_data_json(tmp_path, entries)
    old_img = _make_image(tmp_path, 'Bänder-Becken-Dorsal-clean.jpg')
    new_img = _make_image(tmp_path, 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg')

    migrate_images.migrate(tmp_path, apply=True)

    assert old_img.exists()   # not renamed (target already existed)
    assert new_img.exists()
    updated = json.loads(data_json.read_text(encoding='utf-8'))
    assert updated[0]['filename'] == 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'


def test_apply_warns_when_source_missing_but_still_updates_json(tmp_path, capsys):
    entries = [{'og_filename': 'Anatomie 1-Bänder-Becken-Dorsal.png',
                'filename': 'Bänder-Becken-Dorsal-clean.jpg'}]
    data_json = _make_data_json(tmp_path, entries)
    # No image file created → source missing

    migrate_images.migrate(tmp_path, apply=True)

    captured = capsys.readouterr()
    assert 'WARN' in captured.out or 'warn' in captured.out.lower()
    updated = json.loads(data_json.read_text(encoding='utf-8'))
    assert updated[0]['filename'] == 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'
```

- [ ] **Step 1.2: Tests laufen lassen (müssen FAIL sein)**

```bash
cd "/home/diem/PT Lernkarten/pipeline"
../.venv/bin/pytest tests/test_migrate_images.py -v 2>&1 | head -30
```

Erwartet: `ModuleNotFoundError: No module named 'migrate_images'`

- [ ] **Step 1.3: Script implementieren**

Erstelle `pipeline/migrate_images.py`:

```python
#!/usr/bin/env python3
"""Migrate clean image filenames to include subject prefix.

Usage:
  python migrate_images.py               # dry-run (shows planned changes)
  python migrate_images.py --apply       # apply changes
"""
import argparse
import json
import shutil
from pathlib import Path

DEFAULT_WEB = Path(__file__).parent.parent / 'web'


def _derive_clean_name(og_filename: str) -> str:
    return Path(og_filename).stem + '-clean.jpg'


def migrate(web_dir: Path, apply: bool) -> None:
    data_json = web_dir / 'data' / 'data.json'
    images_dir = web_dir / 'data' / 'images'

    entries = json.loads(data_json.read_text(encoding='utf-8'))

    if apply:
        backup = data_json.with_name('data.json.bak')
        shutil.copy2(data_json, backup)
        print(f'Backup: {backup}')

    any_change = False
    for entry in entries:
        old_name = entry['filename']
        new_name = _derive_clean_name(entry['og_filename'])

        if old_name == new_name:
            continue

        any_change = True
        old_path = images_dir / old_name
        new_path = images_dir / new_name

        if new_path.exists():
            print(f'  SKIP_RENAME (target exists): {old_name} → {new_name}')
            if apply:
                entry['filename'] = new_name
        elif old_path.exists():
            print(f'  RENAME: {old_name} → {new_name}')
            if apply:
                old_path.rename(new_path)
                entry['filename'] = new_name
        else:
            print(f'  WARN (source missing): {old_name} → {new_name}')
            if apply:
                entry['filename'] = new_name

    if not any_change:
        print('No changes needed.')
        return

    if apply:
        data_json.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
        print('data.json updated.')
    else:
        print('\nDry-run: no changes applied. Use --apply to apply.')


def main():
    parser = argparse.ArgumentParser(
        description='Migrate clean image filenames to include subject prefix'
    )
    parser.add_argument('--apply', action='store_true',
                        help='Apply changes (default: dry-run)')
    parser.add_argument('--web', type=Path, default=DEFAULT_WEB,
                        help=f'Path to web/ directory (default: {DEFAULT_WEB})')
    args = parser.parse_args()
    migrate(args.web, apply=args.apply)


if __name__ == '__main__':
    main()
```

- [ ] **Step 1.4: Tests laufen lassen (müssen PASS sein)**

```bash
cd "/home/diem/PT Lernkarten/pipeline"
../.venv/bin/pytest tests/test_migrate_images.py -v
```

Erwartet: alle Tests grün

- [ ] **Step 1.5: Migration dry-run auf echten Daten ausführen (prüfen)**

```bash
cd "/home/diem/PT Lernkarten/pipeline"
python migrate_images.py
```

Prüfen: Ausgabe zeigt die geplanten Umbenennnungen ohne Fehler. Noch keine Datei geändert.

- [ ] **Step 1.6: Commit**

```bash
cd "/home/diem/PT Lernkarten"
git add pipeline/migrate_images.py pipeline/tests/test_migrate_images.py
git commit -m "feat: add migrate_images.py for uniform clean-image naming"
```

---

## Task 2: `convert_text.py` – BILD-Meta-Zeile + Bildfeld in JSON

**Files:**
- Modify: `pipeline/convert_text.py`
- Create: `pipeline/tests/test_convert_text.py`

- [ ] **Step 2.1: Failing tests schreiben**

Erstelle `pipeline/tests/test_convert_text.py`:

```python
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from pathlib import Path
import convert_text
from convert_text import _extract_image_meta, _build_entry, _split_answers


# ── _extract_image_meta ───────────────────────────────────────────────────────

def test_extract_no_bild_row():
    rows = [('Muskel', 'Ursprung', 'Ansatz'), ('M. gluteus maximus', 'Os ilium', 'Femur')]
    meta, remaining = _extract_image_meta(rows)
    assert meta is None
    assert remaining is rows


def test_extract_empty_rows():
    meta, remaining = _extract_image_meta([])
    assert meta is None
    assert remaining == []


def test_extract_bild_row_lowercase():
    rows = [('bild', 'Anatomie 1-Bänder-Becken-Dorsal.png'), ('Muskel', 'Ursprung')]
    meta, remaining = _extract_image_meta(rows)
    assert meta['og'] == 'Anatomie 1-Bänder-Becken-Dorsal.png'
    assert meta['clean'] == 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'
    assert len(remaining) == 1
    assert remaining[0][0] == 'Muskel'


def test_extract_bild_row_uppercase():
    rows = [('BILD', 'Anatomie 1-Knochen-Becken-Ventral (Mann).png'), ('Muskel', 'Ursprung')]
    meta, remaining = _extract_image_meta(rows)
    assert meta['og'] == 'Anatomie 1-Knochen-Becken-Ventral (Mann).png'
    assert meta['clean'] == 'Anatomie 1-Knochen-Becken-Ventral (Mann)-clean.jpg'


def test_extract_bild_row_mixed_case():
    rows = [('Bild', 'Anatomie 1-Test.png'), ('H', 'A')]
    meta, _ = _extract_image_meta(rows)
    assert meta is not None


def test_extract_bild_only_row_exits():
    rows = [('BILD', 'Anatomie 1-Test.png')]
    with pytest.raises(SystemExit):
        _extract_image_meta(rows)


def test_extract_bild_empty_b1_exits(monkeypatch):
    rows = [('BILD', ''), ('Header', 'Col')]
    with pytest.raises(SystemExit):
        _extract_image_meta(rows)


def test_extract_bild_none_b1_exits():
    rows = [('BILD', None), ('Header', 'Col')]
    with pytest.raises(SystemExit):
        _extract_image_meta(rows)


def test_extract_bild_no_extension_exits():
    rows = [('BILD', 'kein-punkt-im-namen'), ('Header', 'Col')]
    with pytest.raises(SystemExit):
        _extract_image_meta(rows)


# ── _build_entry with image ───────────────────────────────────────────────────

def _meta():
    return {'subject': 'Anatomie 1', 'category': 'Muskeln', 'subcategory': 'Gesäß', 'view': 'Gluteus'}

def _rows():
    return [('M. gluteus maximus', 'Os ilium; Os sacrum')]

def _headers():
    return ['Muskel', 'Ursprung']


def test_build_entry_no_image():
    entry = _build_entry(_meta(), _headers(), _rows())
    assert 'image' not in entry


def test_build_entry_with_image():
    image = {'og': 'Anatomie 1-Bänder-Becken-Dorsal.png',
             'clean': 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'}
    entry = _build_entry(_meta(), _headers(), _rows(), image=image)
    assert entry['image']['og'] == 'Anatomie 1-Bänder-Becken-Dorsal.png'
    assert entry['image']['clean'] == 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'


def test_build_entry_image_none_not_in_dict():
    entry = _build_entry(_meta(), _headers(), _rows(), image=None)
    assert 'image' not in entry


def test_build_entry_image_key_position():
    """image field appears after view and before columns (dict ordering)."""
    image = {'og': 'x.png', 'clean': 'x-clean.jpg'}
    entry = _build_entry(_meta(), _headers(), _rows(), image=image)
    keys = list(entry.keys())
    assert 'image' in keys
    assert keys.index('image') < keys.index('columns')


# ── Integration: Excel with BILD row ─────────────────────────────────────────

def test_read_excel_with_bild_produces_image_entry(tmp_path):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['BILD', 'Anatomie 1-Muskeln-Gesäß-Gluteus.png'])
    ws.append(['Muskel', 'Ursprung', 'Ansatz'])
    ws.append(['M. gluteus maximus', 'Os ilium', 'Femur'])
    xlsx_path = tmp_path / 'Anatomie 1-Muskeln-Gesäß-Gluteus.xlsx'
    wb.save(xlsx_path)

    all_rows = convert_text._read_excel(str(xlsx_path))
    meta_info, remaining = _extract_image_meta(all_rows)

    assert meta_info['og'] == 'Anatomie 1-Muskeln-Gesäß-Gluteus.png'
    assert meta_info['clean'] == 'Anatomie 1-Muskeln-Gesäß-Gluteus-clean.jpg'
    assert remaining[0][0] == 'Muskel'


def test_read_excel_without_bild_unchanged(tmp_path):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['Muskel', 'Ursprung'])
    ws.append(['M. gluteus maximus', 'Os ilium'])
    xlsx_path = tmp_path / 'Anatomie 1-Muskeln-Gesäß-Gluteus.xlsx'
    wb.save(xlsx_path)

    all_rows = convert_text._read_excel(str(xlsx_path))
    meta_info, remaining = _extract_image_meta(all_rows)

    assert meta_info is None
    assert len(remaining) == 2
```

- [ ] **Step 2.2: Tests laufen lassen (müssen FAIL sein)**

```bash
cd "/home/diem/PT Lernkarten/pipeline"
../.venv/bin/pytest tests/test_convert_text.py -v 2>&1 | head -40
```

Erwartet: `ImportError` oder `AttributeError` für `_extract_image_meta`, `_build_entry` mit `image`-Parameter nicht vorhanden.

- [ ] **Step 2.3: `_read_excel` und `_read_csv` anpassen (nur Rückgabewert ändern)**

In `pipeline/convert_text.py`, ersetze `_read_excel`:

```python
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
```

Ersetze `_read_csv`:

```python
def _read_csv(filepath):
    for delimiter in (';', ',', '\t'):
        with open(filepath, newline='', encoding='utf-8-sig') as f:
            sample = f.read(4096)
            if delimiter in sample:
                break
    with open(filepath, newline='', encoding='utf-8-sig') as f:
        return list(csv.reader(f, delimiter=delimiter))
```

- [ ] **Step 2.4: `_extract_image_meta` hinzufügen**

Füge nach `_split_answers` in `pipeline/convert_text.py` ein:

```python
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
```

Füge am Anfang von `convert_text.py` den Import hinzu (falls nicht vorhanden):

```python
from pathlib import Path
```

- [ ] **Step 2.5: `_build_entry` aktualisieren**

Ersetze die Funktion `_build_entry`:

```python
def _build_entry(meta, headers, data_rows, image=None):
    columns = headers[1:]
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
```

- [ ] **Step 2.6: `main()` aktualisieren**

Ersetze den Block in `main()`, der `_read_excel`/`_read_csv` aufruft und `_build_entry` nutzt:

```python
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
```

- [ ] **Step 2.7: Tests laufen lassen (müssen PASS sein)**

```bash
cd "/home/diem/PT Lernkarten/pipeline"
../.venv/bin/pytest tests/test_convert_text.py -v
```

Erwartet: alle Tests grün

- [ ] **Step 2.8: Bestehende Tests noch grün?**

```bash
cd "/home/diem/PT Lernkarten/pipeline"
../.venv/bin/pytest tests/test_export.py tests/test_process.py -v
```

Erwartet: keine Regression

- [ ] **Step 2.9: Commit**

```bash
cd "/home/diem/PT Lernkarten"
git add pipeline/convert_text.py pipeline/tests/test_convert_text.py
git commit -m "feat: add BILD meta-row support to convert_text.py"
```

---

## Task 3: Frontend – Bild im Text-Quiz anzeigen

**Files:**
- Modify: `web/js/quiz.js:158,219`
- Modify: `web/js/app.js:71,73`
- Modify: `web/css/style.css:458`

*(Kein automatisierter Test – manuelle Verifikation mit lokalem Webserver)*

- [ ] **Step 3.1: CSS-Klasse hinzufügen**

In `web/css/style.css`, ersetze (präziser Anker vor der Mobile-Media-Query, Zeile 459):

old_string:
```css
/* ══════════════════════════════════════════════
   MOBILE  ≤ 600px
══════════════════════════════════════════════ */
```

new_string:
```css
.tq-quiz-image {
    display: block;
    max-width: 100%;
    max-height: 40vh;
    margin: 0 auto 20px;
    border-radius: 4px;
    object-fit: contain;
}

/* ══════════════════════════════════════════════
   MOBILE  ≤ 600px
══════════════════════════════════════════════ */
```

Dann, für den mobilen Override, ersetze am Ende der Datei (letzten paar Zeilen):

old_string:
```css
    #quiz-img {
        max-height: calc(100vh - 48px);
        max-height: calc(100lvh - 48px); /* lvh bleibt beim Öffnen der Tastatur stabil */
    }
}
```

new_string:
```css
    #quiz-img {
        max-height: calc(100vh - 48px);
        max-height: calc(100lvh - 48px); /* lvh bleibt beim Öffnen der Tastatur stabil */
    }

    .tq-quiz-image {
        max-height: 35vh;
    }
}
```

- [ ] **Step 3.2: `app.js` Aufrufe aktualisieren**

In `web/js/app.js`, Zeilen 71 und 73:

Ersetze:
```javascript
                        loadTextLernen(entry);
```
mit:
```javascript
                        loadTextLernen(entry, OG_IMG_BASE);
```

Ersetze:
```javascript
                        loadTextQuiz(entry);
```
mit:
```javascript
                        loadTextQuiz(entry, IMG_BASE);
```

- [ ] **Step 3.3: `quiz.js` Signaturen und Bild-Rendering aktualisieren**

Zwei präzise Edits in `web/js/quiz.js` – nur die gezeigten old/new Strings ersetzen, restlicher Funktionskörper bleibt unberührt:

**Edit A – `loadTextLernen`** (exakter old→new, Zeile 158–162):

old_string:
```javascript
function loadTextLernen(entry) {
    _currentEntry = null;
    var textWrapper = _textWrapperSetup();

    entry.rows.forEach(function (row) {
        var section = document.createElement('div');
        section.className = 'tq-section';
```

new_string:
```javascript
function loadTextLernen(entry, ogImgBase) {
    _currentEntry = null;
    var textWrapper = _textWrapperSetup();

    if (entry.image) {
        var img = document.createElement('img');
        img.className = 'tq-quiz-image';
        img.alt = '';
        img.src = ogImgBase + entry.image.og;
        img.onerror = function () { img.style.display = 'none'; };
        textWrapper.appendChild(img);
    }

    entry.rows.forEach(function (row) {
        var section = document.createElement('div');
        section.className = 'tq-section';
```

**Edit B – `loadTextQuiz`** (exakter old→new, Zeile 219–225):

old_string:
```javascript
function loadTextQuiz(entry) {
    _currentEntry = null;
    var textWrapper = _textWrapperSetup();

    entry.rows.forEach(function (row) {
        var section = document.createElement('div');
        section.className = 'tq-section';
```

new_string:
```javascript
function loadTextQuiz(entry, imgBase) {
    _currentEntry = null;
    var textWrapper = _textWrapperSetup();

    if (entry.image) {
        var img = document.createElement('img');
        img.className = 'tq-quiz-image';
        img.alt = '';
        img.src = imgBase + entry.image.clean;
        img.onerror = function () { img.style.display = 'none'; };
        textWrapper.appendChild(img);
    }

    entry.rows.forEach(function (row) {
        var section = document.createElement('div');
        section.className = 'tq-section';
```

- [ ] **Step 3.4: Manuelle Verifikation**

```bash
cd "/home/diem/PT Lernkarten/web"
python3 -m http.server 8080
```

Öffne `http://localhost:8080` im Browser und prüfe:

**Ohne Bild (bestehende Tabelle):**
- Beliebige Muskeln-Tabelle aus dem Menü wählen
- Lernen- und Quiz-Modus funktionieren wie zuvor, kein Bild

**Mit Bild (manuelle Vorbereitung nötig):**
1. Öffne `web/data/text-data.json` temporär und füge `"image": {"og": "<existierender-og-name>", "clean": "<existierender-clean-name>"}` zu einem Eintrag hinzu
2. Seite neu laden, Lernen-Modus öffnen → OG-Bild erscheint oben
3. Quiz-Modus öffnen → Clean-Bild erscheint oben
4. Wenn ein Bild fehlt: kein Broken-Image-Icon, Quiz funktioniert normal

**Danach:** temporäre Änderung in text-data.json rückgängig machen (oder lassen, wenn Test-Daten gewünscht)

- [ ] **Step 3.5: Commit**

```bash
cd "/home/diem/PT Lernkarten"
git add web/js/quiz.js web/js/app.js web/css/style.css
git commit -m "feat: render optional image in text quiz (lernen + testen mode)"
```

---

## Task 4: Migration ausführen

*(Erst nach Task 1 – jetzt die echten Daten migrieren)*

- [ ] **Step 4.1: Dry-run auf Produktionsdaten**

```bash
cd "/home/diem/PT Lernkarten/pipeline"
python migrate_images.py
```

Ausgabe prüfen: alle geplanten Umbenennungen plausibel?

- [ ] **Step 4.2: Migration anwenden**

```bash
python migrate_images.py --apply
```

Ausgabe prüfen: keine WARN-Meldungen (alle Quelldateien gefunden)

- [ ] **Step 4.3: App nach Migration prüfen**

```bash
cd "/home/diem/PT Lernkarten/web"
python3 -m http.server 8080
```

Öffne `http://localhost:8080` → Bild-Quiz (Anatomie-Knochen etc.) laden und prüfen, dass Bilder noch korrekt angezeigt werden.

- [ ] **Step 4.4: Geänderte Daten committen**

```bash
cd "/home/diem/PT Lernkarten"
git add web/data/data.json web/data/images/
git commit -m "chore: migrate clean image filenames to include subject prefix"
```

---

## Abschluss-Checkliste

- [ ] Alle Pipeline-Tests grün: `../.venv/bin/pytest pipeline/tests/ -v --ignore=pipeline/tests/test_ocr.py --ignore=pipeline/tests/test_inpaint.py --ignore=pipeline/tests/test_semantic_classify.py`
- [ ] Bilder in Image-Quiz nach Migration noch korrekt
- [ ] Text-Quiz ohne Bild: kein Fehler, unverändert
- [ ] Text-Quiz mit Bild: OG oben in Lernen, Clean oben in Testen, onerror blendet fehlendes Bild stumm aus

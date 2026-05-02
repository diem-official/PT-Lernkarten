# Design: OCR-VLM Pipeline Refactor — Zwischenspeicherung, Inpainting-Fix, QM-Report

**Datum:** 2026-05-02  
**Status:** Genehmigt  
**Ansatz:** A (minimaler Umbau)

## Ziel

Die Worterkennung-Pipeline wird in drei klar getrennte Schritte unterteilt:
1. OCR erkennt Wörter und zeichnet rote Bounding Boxes → speichert Zwischenbilder für menschliche QS
2. VLM gruppiert Begriffe, führt zwei QM-Prüfungen durch und schreibt einen Report
3. Finales Inpainting legt weiße Masken über valide Wörter im Originalbild

## Verzeichnisstruktur

```
/Output/
  <stem>-marked.jpg     # rote Bounding Boxes, ein Bild pro Eingabedatei
  report.json           # aggregierte QM-Ergebnisse aller verarbeiteten Bilder

web/data/images/
  <stem>-clean.jpg      # finales Bild mit weißen Masken (unverändert)
```

`/Output` wird von `process.py` nach dem `if not all_files: sys.exit(0)` Check angelegt.

## Geänderte Dateien

### `pipeline/inpaint.py`

`remove_text()` wird durch zwei explizite Funktionen ersetzt und komplett entfernt:

- `draw_boxes(image: Image.Image, blocks: list) -> Image.Image` — zeichnet rote Umrisse (3px, `outline=(255,0,0)`) mit hardcoded 5px Padding um jeden Block. Nicht `BOX_PADDING` verwenden.
- `mask_text(image: Image.Image, blocks: list) -> Image.Image` — füllt jeden Block mit einem soliden weißen Rechteck (`fill=(255,255,255)`, hardcoded 5px Padding). Nicht `BOX_PADDING` verwenden.

Beide Funktionen arbeiten auf `image.copy()` und verändern das Original nicht.

### `pipeline/vlm_classify.py` — minimale Erweiterung

Nur eine Änderung: Im `except`-Block von `detect_labels()` wird das zurückgegebene Dict um `"error": True` erweitert:

```python
# im except-Block (aktuell: return _empty):
return {**_empty, "error": True}
# Normalfall: _empty ohne "error"-Key
```

`process.py` prüft: `vlm_failed = bool(vlm_result.get("error", False))`

### `pipeline/ocr.py`

Alle `log.info("DEBUG …")` Zeilen (Präfix `"DEBUG"`) in `extract_labels()` werden entfernt. Signatur und Rückgabewert unverändert.

### `pipeline/process.py`

**Neuer Import:**
```python
import json   # hinzufügen — wird für _write_report benötigt
```

**Import-Änderung:**
```python
# Alt:
from inpaint import remove_text
# Neu:
from inpaint import draw_boxes, mask_text
```

**Neue private Hilfsfunktion (vor `main`):**
```python
def _write_report(entries: list, path: Path) -> None:
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
```

**Initialisierung (nach `if not all_files` Check):**
```python
output_dir = Path(__file__).parent.parent / 'Output'
output_dir.mkdir(parents=True, exist_ok=True)
```

**Pass 1 (OCR) — Erweiterung:**

```python
marked_images: dict[Path, Image.Image] = {}   # vor dem Loop
```

Pro Bild (nach erfolgreichem OCR):
```python
with Image.open(path) as img:
    rgb = img.convert('RGB')
marked = draw_boxes(rgb, ocr_blocks)
marked.save(output_dir / f"{path.stem}-marked.jpg", 'JPEG', quality=95)
marked_images[path] = marked
ocr_results[path] = ocr_blocks
```

Bilder mit 0 OCR-Blöcken: kein `marked_image`, kein Report-Eintrag.

**Pass 2 (VLM) — Erweiterung:**

```python
qm_entries: list[dict] = []   # vor dem Loop
```

Die bestehende Zeile `image = Image.open(path).convert('RGB')` am Anfang der Pass-2-Loop wird entfernt — Pass 3 öffnet das Original selbst neu.

Struktur der Pass-2-Loop (Reihenfolge ist entscheidend):

```python
vlm_result = detect_labels(marked_images[path], ocr_blocks)

vlm_failed = bool(vlm_result.get("error", False))
invalid_ids = set(vlm_result["invalid_ocr_ids"])   # set → keine Duplikate

# Warnings
if vlm_result["missing_words_detected"]:
    log.warning(...)
if invalid_ids:
    log.warning(...)   # hochgesetzt von info → warning

valid_blocks = [b for b in ocr_blocks if b["id"] not in invalid_ids]
groupings = vlm_result["groupings"]

# labels bauen (kann leer sein)
block_by_id = {b["id"]: b for b in valid_blocks}
labels = []
for g in groupings:
    blocks = [block_by_id[i] for i in g["ocr_ids"] if i in block_by_id]
    if not blocks:
        log.warning(...)
        continue
    ...
    labels.append(...)

# QM-Eintrag IMMER schreiben (auch wenn labels leer)
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

# Nur zum Inpainting weitergehen wenn labels vorhanden
if not labels:
    print(f"  → No valid labels after filtering, skipping")
    continue

# Pass 3: Inpainting
image = Image.open(path).convert('RGB')   # frisches Original
clean = mask_text(image, valid_blocks)
...
```

Die alten Checks `if not groupings: continue` und `if not labels: continue` werden durch die obige Struktur ersetzt — QM-Append kommt vor dem `continue`.

**Nach der Loop:** `_write_report(qm_entries, output_dir / 'report.json')`

## report.json Format

```json
[
  {
    "image": "Knochen-Os sacrum-ventral",
    "ocr_block_count": 12,
    "missing_words_detected": false,
    "invalid_ocr_ids": [3],
    "invalid_ocr_texts": ["."],
    "valid_block_count": 11,
    "groupings_count": 5,
    "vlm_failed": false
  }
]
```

`valid_block_count` = `len(ocr_blocks) - len(set(invalid_ocr_ids))`.  
`groupings_count` = `len(labels)` nach dem internen `if not blocks: continue` Filter.  
Eintrag erscheint für jedes Bild mit ≥1 OCR-Block, auch wenn `groupings_count=0`.

## Tests

### `pipeline/tests/test_inpaint.py` — Datei komplett überschreiben

Die bestehende Datei importiert `create_mask` (existiert nicht) — sie muss vollständig ersetzt werden:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PIL import Image
from inpaint import draw_boxes, mask_text


def _block(x, y, w, h):
    return {"id": 0, "x": x, "y": y, "w": w, "h": h, "text": "T"}


def test_draw_boxes_returns_copy():
    img = Image.new("RGB", (100, 100), (200, 200, 200))
    assert draw_boxes(img, [_block(10, 10, 20, 20)]) is not img


def test_draw_boxes_marks_border_pixel_red():
    # draw_boxes uses outline — sample border pixel at (5,5) after 5px padding on block at (10,10)
    img = Image.new("RGB", (100, 100), (200, 200, 200))
    result = draw_boxes(img, [_block(10, 10, 20, 20)])
    assert result.getpixel((5, 5))[0] > 200


def test_mask_text_returns_copy():
    img = Image.new("RGB", (100, 100), (200, 200, 200))
    assert mask_text(img, [_block(10, 10, 20, 20)]) is not img


def test_mask_text_whites_out_center():
    img = Image.new("RGB", (100, 100), (0, 0, 0))
    assert mask_text(img, [_block(10, 10, 20, 20)]).getpixel((20, 20)) == (255, 255, 255)
```

### `pipeline/tests/test_process.py` — an bestehende Datei anhängen

Der bestehende `sys.path`-Header (Zeilen 1–3) bleibt. Folgendes wird am Ende der Datei angefügt:

```python
import json
from process import _write_report


def test_write_report(tmp_path):
    _write_report([{"image": "test", "ocr_block_count": 5}], tmp_path / "report.json")
    data = json.loads((tmp_path / "report.json").read_text())
    assert data[0]["image"] == "test"


def test_write_report_overwrites(tmp_path):
    p = tmp_path / "report.json"
    _write_report([{"image": "old"}], p)
    _write_report([{"image": "new"}], p)
    assert json.loads(p.read_text())[0]["image"] == "new"
```

## Nicht geändert (außer explizit oben)

- `export.py` — unverändert
- Web-Output-Pfad `web/data/images/` — unverändert
- GPU-Memory-Management (`unload_engine`, `unload_model`) — unverändert
- `BOX_PADDING = 8` in `process.py` — bleibt für `_union_box`; `draw_boxes`/`mask_text` nutzen hardcoded 5px
- `_parse_stem` — unverändert

## Kritischer Bug (wird behoben)

`remove_text()` zeichnet rote Umrisse. Sie wird in `process.py` sowohl für den VLM-Input als auch für das finale "saubere" Bild aufgerufen — das Endbild enthält dadurch rote Rahmen statt weißer Masken. Der Fix: `mask_text()` für Pass 3, `draw_boxes()` für Pass 1.

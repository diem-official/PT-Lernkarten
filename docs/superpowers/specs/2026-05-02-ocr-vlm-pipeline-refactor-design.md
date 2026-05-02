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

`/Output` wird von `process.py` beim Start angelegt, falls nicht vorhanden.

## Geänderte Dateien

### `pipeline/inpaint.py`

`remove_text()` wird durch zwei explizite Funktionen ersetzt:

- `draw_boxes(image, blocks) -> Image` — zeichnet rote Umrisse (3px) mit 5px Padding um jeden Block. Wird für VLM-Input und Speicherung nach `/Output` genutzt.
- `mask_text(image, blocks) -> Image` — füllt jeden Block mit einem soliden weißen Rechteck (5px Padding). Wird für das finale Bild genutzt.

Beide Funktionen arbeiten auf einer Kopie des Eingabebilds und verändern das Original nicht.

### `pipeline/ocr.py`

- Alle temporären DEBUG-Log-Zeilen (Zeilen 53–92: Schema-Dump, Box-Alignment, Preprocessor-Info) werden entfernt.
- `extract_labels()` Signatur und Rückgabewert bleiben unverändert.

### `pipeline/process.py`

**Pass 1 (OCR) — Erweiterung:**
- Nach OCR: `draw_boxes(image, ocr_blocks)` → in Memory als `marked_image`
- `marked_image` nach `/Output/<stem>-marked.jpg` speichern (JPEG, quality=95)
- `marked_image` wird in Memory für Pass 2 weitergegeben (kein zweites Einlesen)

**Pass 2 (VLM) — Erweiterung:**
- `invalid_ocr_ids` Log-Level von `log.info` auf `log.warning` hochsetzen
- `missing_words_detected` bleibt `log.warning` (bereits korrekt)
- Pro Bild ein QM-Dict aufbauen:
  ```python
  {
      "image": stem,
      "ocr_block_count": len(ocr_blocks),
      "missing_words_detected": bool,
      "invalid_ocr_ids": list[int],
      "invalid_ocr_texts": list[str],   # text-Felder der ungültigen Blöcke
      "valid_block_count": int,
      "groupings_count": int,
  }
  ```
- Nach Abschluss aller Bilder: `report.json` nach `/Output/report.json` schreiben (überschreibt vorherige)

**Pass 3 (Inpainting) — Fix:**
- Aktuell: `remove_text(image, valid_blocks)` → zeichnet fälschlicherweise rote Boxen ins Endbild
- Neu: `mask_text(image, valid_blocks)` → weiße Masken
- Nur `valid_blocks` (ohne `invalid_ocr_ids`) werden maskiert

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
    "groupings_count": 5
  }
]
```

## Nicht geändert

- `vlm_classify.py` — VLM-Prompt, Modell-Loading, Response-Parsing bleiben unverändert
- `export.py` — unverändert
- Web-Output-Pfad `web/data/images/` — unverändert
- GPU-Memory-Management — unverändert

## Kritischer Bug (wird behoben)

`remove_text()` in `inpaint.py` zeichnet rote Umrisse. In `process.py` wird dieselbe Funktion sowohl für den VLM-Input als auch für das finale "saubere" Bild aufgerufen. Das finale Bild enthält dadurch rote Rahmen statt weißer Masken. Der Fix ist die Einführung von `mask_text()` und die Anpassung des Aufrufs in Pass 3.

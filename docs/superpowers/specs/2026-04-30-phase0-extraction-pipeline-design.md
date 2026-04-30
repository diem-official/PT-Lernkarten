# Phase 0 Extraction Pipeline — Design Spec

**Date:** 2026-04-30
**Status:** Approved

---

## Goal

Automatically extract anatomical diagrams from the Prometheus PDF, classify them using a local VLM, and save them to `Pics/` using the project's strict `Kategorie-Unterkategorie-Ansicht.jpg` naming convention. Output feeds directly into the existing Phase 1 pipeline (`pipeline/process.py`).

---

## Constraints

- Runs entirely locally — no external APIs
- Hardware: Threadripper 3970x, 128 GB RAM, RTX 3090 Ti (24 GB VRAM)
- Must be crash-resistant: log errors per image, skip and continue
- PDF: `Buch/PROMETHEUS Allgemeine Anatomie und Bewegungssystem…pdf` (born-digital, 646 pages)
- Output directory: `Pics/`

---

## Architecture

```
PDF
 │  PyMuPDF image-block detection  (pipeline/pdf_extract.py)
 ▼
(page_no, image_index, PIL.Image at 300 DPI)
 │  Qwen2.5-VL-7B-Instruct         (pipeline/vlm_classify.py)
 ▼
{"is_anatomical": bool, "category": str, "subcategory": str, "view": str}
 │  orchestration + file save      (pipeline/phase0_runner.py)
 ▼
Pics/Kategorie-Unterkategorie-Ansicht.jpg
```

### File Layout

```
PT Lernkarten/
├── phase0_extract.py          ← CLI entry point
├── Buch/                      ← source PDF
├── Pics/                      ← output (created on first run)
├── pipeline.log               ← written at project root
└── pipeline/
    ├── pdf_extract.py         ← new
    ├── vlm_classify.py        ← new
    ├── phase0_runner.py       ← new
    ├── requirements.txt       ← extended
    └── … existing modules unchanged …
```

---

## Module Specifications

### `pipeline/pdf_extract.py`

**Responsibility:** Locate and rasterize figure regions from the PDF.

**Logic:**
1. Open PDF with `fitz.open()`
2. Iterate pages (optionally filtered by a page range)
3. On each page call `page.get_image_info(xrefs=True)` to get image bounding boxes
4. Filter: discard any image whose bounding box is smaller than `min_size × min_size` pixels (default 150)
5. For each qualifying image rect, call `page.get_pixmap(clip=rect, dpi=300)` to rasterize at 300 DPI
6. Convert pixmap to `PIL.Image` and yield `(page_no, img_index, pil_image)`
7. On any per-image exception: log at ERROR, skip — never raise

**Public interface:**
```python
def iter_figures(
    pdf_path: str | Path,
    min_size: int = 150,
    page_range: tuple[int, int] | None = None,
) -> Iterator[tuple[int, int, Image.Image]]:
    ...
```

---

### `pipeline/vlm_classify.py`

**Responsibility:** Load Qwen2.5-VL-7B-Instruct once and classify a figure image.

**Model loading:** Lazy singleton — loaded on first call, reused for all subsequent calls. Loaded in `torch.bfloat16` on CUDA.

**Prompt (system):**
> You are an anatomy atlas classifier. Respond ONLY with a JSON object — no prose, no markdown fences.

**Prompt (user):**
> Look at this image. Keys to return:
> - `is_anatomical` (bool): true if this is an anatomical diagram containing pointer lines or labels
> - `category` (str or null): one of Knochen, Muskeln, Gelenke, Bänder, Gefäße, Nerven, Organe
> - `subcategory` (str or null): e.g. Arm, Bein, Kopf, Rumpf, Becken, Hand, Fuß, Schulter, Hüfte
> - `view` (str or null): e.g. dorsal, ventral, lateral, medial, frontal, superior, inferior
>
> If `is_anatomical` is false, set the other fields to null.

**Output parsing:**
- Extract first `{…}` from response
- Parse JSON; on failure return `None`
- If `is_anatomical` is false or missing → return `None`
- If any of category/subcategory/view is null/empty → return `None`
- Sanitise strings: strip whitespace, title-case category/subcategory, lowercase view, replace spaces with underscores, transliterate Umlauts (ä→ae, ö→oe, ü→ue, ß→ss)

**Public interface:**
```python
def classify(image: Image.Image) -> dict | None:
    """Returns {"category": str, "subcategory": str, "view": str} or None."""
```

---

### `pipeline/phase0_runner.py`

**Responsibility:** Orchestrate extraction → classification → save loop.

**Logic:**
1. Create `output_dir` if it does not exist
2. Call `iter_figures()` for each (page_no, img_idx, image)
3. Pass image to `classify()`; if `None` log at DEBUG with reason, continue
4. Build filename: `{category}-{subcategory}-{view}.jpg`
5. Handle collisions: if filename already exists, append `_2`, `_3`, etc.
6. If `dry_run=True`: log the would-be filename, do not save
7. Otherwise: save as JPEG quality 95
8. Track and return a `RunStats(total, saved, discarded, errors)` dataclass

**Public interface:**
```python
def run(
    pdf_path: str | Path,
    output_dir: str | Path,
    min_size: int = 150,
    page_range: tuple[int, int] | None = None,
    dry_run: bool = False,
) -> RunStats:
    ...
```

---

### `phase0_extract.py` (CLI)

```
python phase0_extract.py --input <pdf> --output <dir>
                         [--min-size 150]
                         [--pages 1-100]
                         [--dry-run]
```

- `--input` — path to PDF (default: `Buch/<first .pdf found>`)
- `--output` — output directory (default: `Pics/`)
- `--min-size` — minimum image dimension in pixels to consider (default: 150)
- `--pages` — page range `START-END` (1-indexed, inclusive); omit for full PDF
- `--dry-run` — classify but do not write files

Exits with code 0 on success, 1 on fatal error (e.g. PDF not found).

---

## Logging

Two handlers on the root logger:
- **Console** — `INFO` level
- **File** (`pipeline.log` at project root) — `DEBUG` level, append mode

Log events:
| Level | Event |
|---|---|
| INFO | Pipeline start, model loaded, each saved file |
| DEBUG | Each discarded image with reason (too small / not anatomical / parse failure) |
| ERROR | Any per-image exception (page, index, exception message) |
| INFO | Final summary: total / saved / discarded / errors |

---

## Requirements additions (`pipeline/requirements.txt`)

```
PyMuPDF>=1.24
transformers>=4.49
qwen-vl-utils>=0.0.8
accelerate>=0.27
Pillow>=10.0
```

Torch is already present in the venv (`2.11.0+cu126`).

---

## Filename Collision Strategy

If `Knochen-Arm-dorsal.jpg` already exists in `Pics/`, the next one becomes `Knochen-Arm-dorsal_2.jpg`, then `_3`, etc. This preserves all variants (e.g. two dorsal arm views from different pages).

---

## Error Handling Policy

- PDF not found → fatal, exit 1
- Model load failure → fatal, exit 1
- Per-page rasterization error → log ERROR, skip page
- Per-image VLM error → log ERROR, skip image
- Per-image JSON parse failure → log DEBUG, discard
- File write error → log ERROR, skip (do not crash)

---

## Out of Scope

- Phase 1 OCR/inpainting (unchanged)
- Deduplication of near-identical crops across pages
- Fine-tuning the VLM
- Web app changes

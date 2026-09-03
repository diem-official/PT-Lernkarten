# PT Lernkarten – Anatomy Flashcard System

An interactive anatomy study tool for physiotherapy. Two content types feed one
shared menu:

- **Image quizzes** — place labelled anatomy images in `Input/`; the pipeline
  detects each text label, whites it out, and records its position so the web
  app can quiz the terms on the cleaned image.
- **Text quizzes** — an Excel or CSV table of questions and answers is converted
  to JSON; the web app renders it as a multi-answer input quiz.

Every topic offers three study modes, chosen per view in the menu:

| Mode | Image quiz | Text quiz |
|---|---|---|
| **Lernen** | shows the original **labelled** image, zoomable | shows all questions with all answers as static text |
| **Schreiben** | type each term into a numbered panel; live prefix validation | type answers into per-category fields; multi-answer pool logic |
| **Quiz** | flashcard self-assessment ("Wie heißt Nummer *n*?" → *Korrekt/Falsch*) | flashcard self-assessment per (row × category), from a separate verbose answer file |

---

## Architecture

```
Bilder/ (raw photos, optional)
        │  auto-resize ≤2500px, apply EXIF rotation
        ▼
Input/ (labelled images)              Tabellen/ (Excel / CSV)
        │                                     │
        ▼                                     ▼
┌────────────────────────────┐    ┌────────────────────────┐
│  pipeline/process.py         │    │  pipeline/convert_text.py │
│  OCR → term extraction        │    │  table → JSON             │
│  → whiteout → JSON export      │    │                           │
└────────────────────────────┘    └────────────────────────┘
        │                                     │
        ▼                                     ▼
   web/data/data.json                 web/data/text-data.json
   web/data/images/    (cleaned)      web/data/text-quiz-data.json  (verbose, hand-maintained)
   web/data/og-images/ (originals)
        │                                     │
        └──────────────────┬──────────────────┘
                           ▼
                ┌─────────────────────┐
                │   Static Web App    │   no backend, no build step
                │   (HTML / CSS / JS) │   deployed to GitHub Pages
                └─────────────────────┘
```

---

## Phase 1a – Image Pipeline (`pipeline/process.py`)

### What it does

The run is incremental: images whose filename stem is already present in
`web/data/data.json` are skipped, so re-running only processes new files.

1. **Preprocessing** — if `Bilder/` exists (path is currently hard-coded in
   `process.py` as `RAW_IMAGES_DIR`), every image there is EXIF-rotation-corrected
   and downscaled to a max dimension of 2500 px into the input directory.
2. **Pass 1 – OCR** (`ocr.py`) — PaddleOCR (`lang='german'`) returns every text
   block as `{id, x, y, w, h, text}`. Low-confidence (< 0.3) results are dropped.
   A debug image with every box outlined is written to `Output/<stem>-marked.jpg`.
3. **Pass 2 – Term extraction** (`semantic_classify.py`)
   - Noise filter: single-character and non-alphabetic blocks are dropped.
   - Size-outlier filter: blocks more than 3.5× taller than the median line
     (usually illustration hatching misread as text) are dropped.
   - `detect_labels()` builds an association graph over the remaining blocks
     from geometric proximity/alignment, an NLP score, and — when the source
     image is available — leader-line evidence (OpenCV Canny + `HoughLinesP`).
     Connected components are fused with `networkx` so a multi-line caption
     becomes one term.
   - Each term gets an `anchor` point and a padded union `mask_box`.
   - Orphaned terms and unmatched OCR blocks are logged and recorded in
     `Output/report.json` for manual review.
4. **Pass 3 – Whiteout** (`inpaint.py`) — `mask_text()` paints white rectangles
   (+5 px padding) over every accepted OCR block. There is **no** neural
   inpainting; the cleaned image is saved as `web/data/images/<stem>-clean.jpg`
   and the untouched original is copied to `web/data/og-images/<name>`.
5. **Export** (`export.py`) — merges the new entries into `web/data/data.json`.

### File naming convention

```
Fach-Kategorie-Unterkategorie-Ansicht.{jpg,jpeg,png,tif,tiff}
```

Exactly three hyphens; none of the four parts may contain a hyphen (spaces are
fine). Example:

`Anatomie 1-Knochen-Becken-Dorsal (Frau).png`
→ menu entry **Anatomie 1 › Knochen › Becken › Dorsal (Frau)**

Files that don't match are skipped with a warning.

### Setup

```bash
# 1. Install PaddlePaddle GPU (match your CUDA version) — see pipeline/requirements.txt
#    for the exact index URLs.
# 2. Install the rest:
pip install -r pipeline/requirements.txt
```

The pipeline needs `paddleocr`, `opencv-python`, `Pillow`, `numpy`, `networkx`
and `openpyxl`.

### Run

```bash
python pipeline/process.py [input_dir] [--output-web <path_to_web/>]
```

- `input_dir` — folder with source images (default: `Input/`).
- `--output-web` — path to the `web/` directory (default: repo-root `web/`).

---

## Phase 1b – Text Converter (`pipeline/convert_text.py`)

Converts an Excel or CSV table into `web/data/text-data.json` so text quizzes
appear in the same menu as image quizzes.

### Table format

| Name *(first column)* | Kategorie A | Kategorie B | … |
|---|---|---|---|
| Frage / Subjekt | Antwort | Antwort1; Antwort2 | … |

- **Row 1** — column headers. The first header is the subject label; every other
  header becomes an answer category shown above its input field(s).
- **Row 2+** — one question per row. First cell = question; other cells =
  answers, multiple answers separated by `;`.
- **Answer prefixes** — an answer written as `Präfix: Wert` (e.g.
  `Hüfte: Flexion`) is displayed with the prefix as a fixed label. Several
  answers sharing a prefix in the same cell form their own sub-pool.
- **Optional `BILD` row** — if cell `A1` is `BILD`, cell `B1` must hold an image
  filename (with extension). The header row then starts in row 2, and the entry
  gets an `image: { og, clean }` reference that the web app renders next to the
  quiz. (Two-image views use an `images: [ … ]` array, added by hand.)

### File naming convention (same as images)

```
Fach-Kategorie-Unterkategorie-Ansicht.{xlsx,csv}
```

Example: `Anatomie 1-Muskeln Detail-Gesäß-Gluteus.xlsx`
→ menu entry **Anatomie 1 › Muskeln Detail › Gesäß › Gluteus**

### Run

```bash
python pipeline/convert_text.py "Tabellen/Anatomie 1-Muskeln Detail-Gesäß-Gluteus.xlsx" [--output <path>]
```

Re-running on the same file replaces the existing entry (matched by
subject/category/subcategory/view), so there are no duplicates.

> `text-quiz-data.json` (used by the **Quiz** mode) is **not** produced by this
> script — it is maintained by hand (see below).

---

## Phase 2 – Web App (`web/`)

A fully static, client-side application. `web/index.html` loads three JSON files
in parallel; only `data.json` is required, the two text files fall back to `[]`.

> The page title and mobile header currently read **"4 Gewinnt"** — a
> placeholder joke, not a bug.

### Running locally

```bash
cd web
python3 -m http.server 8080
# open http://localhost:8080
```

### Menu & layout

`menu.js` builds a four-level accordion (Fach › Kategorie › Unterkategorie ›
Ansicht) from the combined image + text entries. Each Ansicht row carries three
buttons — **Lernen / Schreiben / Quiz** — wired in `app.js` to the loader for
that content type and mode.

- **Desktop/tablet** (> 600 px): fixed left sidebar, collapsible via the header
  button (state saved in `localStorage`, key `ptl-sidebar-collapsed`).
- **Mobile** (≤ 600 px): the sidebar becomes a slide-in drawer opened by the
  hamburger button; `visualViewport` is used to keep the image visible when the
  on-screen keyboard opens.
- The image/answer split follows viewport **orientation**: answer panel to the
  right in landscape, below in portrait.

### Image quiz

**Lernen** — loads the original **labelled** image from `og-images/`. No inputs;
pan/zoom via `zoom.js` (wheel, pinch, double-tap).

**Schreiben** — loads the cleaned image and draws a numbered marker at each
label's `mask_box` centre (scaled to the rendered size). The numbered answer
rows live in a separate panel, matched by number. Validation runs on every
keystroke:

| State | Visual |
|---|---|
| Exact full match (case-insensitive) | Green, field locked |
| Prefix of the solution | Green gradient (opacity = progress) |
| Not a prefix | Orange |

Matching is exact: the full term must be spelled correctly (case aside) for the
field to lock — there is deliberately no typo tolerance.

Each row has a `?` button opening a modal with the correct term. On window
**resize**, only the marker positions recalculate; the answer panel keeps all
field values, colours and locked state.

**Quiz** (`quiz-abfrage.js`) — pick an order (*Der Reihe nach* / *Zufällig*),
then answer one structure at a time: "Wie heißt die Struktur mit der Nummer
*n*?" → *Antwort* reveals the term → you self-assess *Korrekt* / *Falsch*.
Wrong answers are re-queued to the end. A counter shows "*X* von *N* offen".

### Text quiz

**Lernen** (`loadTextLernen`) — a scrollable list: each question with every
answer of every category shown as static text, plus the optional image(s).

**Schreiben** (`loadTextQuiz`) — one input group per answer category.
Multi-answer **pool logic**: each category tracks the still-unclaimed answers.
When a field is completed correctly, that answer is claimed and removed from the
pool; the other fields then accept only the remaining answers, in any order.
Prefixed answers (`Präfix: Wert`) get a fixed label; a group of same-prefix
answers has its own pool. The `?` button (per category) reveals one random
unclaimed answer, or "Alle Antworten korrekt ✓" when done.

Example with 3 answers `["A", "B", "C"]`:
- Type "B" in field 1 → B is claimed, pool becomes `[A, C]`.
- Fields 2 and 3 now accept only "A" or "C".

**Quiz** (`text-quiz-abfrage.js`) — uses `text-quiz-data.json` (more verbose
answers than `text-data.json`), matched to the menu entry by
subject/category/subcategory/view. Pick an order (*Der Reihe nach* / *Zufällig*
/ *Aus Liste*), then for each (row × category) pair: read the question → reveal
the answer → self-assess *Korrekt* / *Falsch*. *Aus Liste* shows every question
grouped by row and lets you pick freely in a pop-up. If no matching entry
exists, the mode shows "Noch keine Quiz-Daten für diese Ansicht vorhanden."

---

## Project Structure

```
PT Lernkarten/
├── Input/                      # source images (git-ignored)
├── Bilder/                     # raw photos, pre-resized into Input/ (git-ignored)
├── Tabellen/                   # Excel / CSV quiz tables
├── Output/                     # pipeline debug output: *-marked.jpg, report.json (git-ignored)
├── docs/superpowers/           # design specs and implementation plans
├── System Architektur.md       # early architecture notes (partly outdated)
├── .github/workflows/deploy.yml # GitHub Pages deploy
├── pipeline/
│   ├── process.py              # image pipeline CLI
│   ├── ocr.py                  # PaddleOCR wrapper
│   ├── semantic_classify.py    # graph-based term extraction (used by process.py)
│   ├── logic_classify.py       # alternative deterministic term extraction (not wired in)
│   ├── inpaint.py              # box drawing + whiteout
│   ├── export.py               # build_entry / save_data_json
│   ├── convert_text.py         # Excel/CSV → text-data.json
│   ├── migrate_images.py       # one-off: uniform clean-image naming
│   ├── migrate_to_fach.py      # one-off: 3-part → 4-part (Fach prefix) migration
│   ├── requirements.txt
│   └── tests/                  # pytest (run from inside pipeline/)
└── web/
    ├── index.html
    ├── css/style.css
    ├── js/
    │   ├── app.js              # bootstrap, fetch, routing
    │   ├── menu.js             # accordion menu builder
    │   ├── quiz.js             # image + text: Lernen & Schreiben modes
    │   ├── quiz-abfrage.js     # image: Quiz mode
    │   ├── text-quiz-abfrage.js# text: Quiz mode
    │   ├── zoom.js             # pan/zoom for images and image overlay
    │   └── levenshtein.js      # Levenshtein distance helper
    └── data/
        ├── data.json           # image quizzes (process.py)
        ├── text-data.json      # text quizzes: Lernen/Schreiben (convert_text.py)
        ├── text-quiz-data.json # text quizzes: Quiz mode (hand-maintained)
        ├── images/             # cleaned images (process.py)
        └── og-images/          # original images (process.py)
```

---

## `data.json` format (image quizzes)

```json
[
  {
    "filename": "Anatomie 1-Bänder-Becken-Dorsal-clean.jpg",
    "og_filename": "Anatomie 1-Bänder-Becken-Dorsal.png",
    "subject": "Anatomie 1",
    "category": "Bänder",
    "subcategory": "Becken",
    "view": "Dorsal",
    "labels": [
      {
        "text": "Crista iliaca",
        "anchor_x": 506, "anchor_y": 156.0,
        "mask_box": { "x": 498, "y": 128, "w": 191, "h": 56 }
      }
    ]
  }
]
```

`anchor_x` / `anchor_y` are exported but the current frontend positions markers
from the `mask_box` centre only.

## `text-data.json` format (text quizzes: Lernen / Schreiben)

```json
[
  {
    "type": "text",
    "subject": "Anatomie 1",
    "category": "Muskeln Detail",
    "subcategory": "Hüfte",
    "view": "Adduktoren",
    "image": {
      "og": "Anatomie 1-Muskeln-Adduktoren-Frontal.png",
      "clean": "Anatomie 1-Muskeln-Adduktoren-Frontal-clean.jpg"
    },
    "columns": ["Ursprung", "Ansatz", "Funktion", "Innervation"],
    "rows": [
      {
        "question": "M. gluteus maximus",
        "answers": {
          "Ursprung": ["Facies glutea: Os ilium", "Lig. sacrotuberale"],
          "Ansatz": ["Tuberositas glutea"],
          "Funktion": ["Hüfte: Extension", "Hüfte: Außenrotation"],
          "Innervation": ["N. gluteus inferior (L5-S2)"]
        }
      }
    ]
  }
]
```

- `image` is optional; a two-image view uses `"images": [ {og, clean}, … ]`.
- `columns` may contain trailing `""` entries (empty categories are ignored).

## `text-quiz-data.json` format (text quizzes: Quiz mode)

Same shape as a `text-data.json` entry **without** `type`, with longer,
explanatory answer strings. Maintained by hand; matched to the corresponding
`text-data.json` entry by `subject` + `category` + `subcategory` + `view`.

---

## Tests

```bash
cd pipeline
python -m pytest
```

Covers OCR parsing, term extraction, whiteout, export, the text converter and
both migration scripts.

---

## Deployment

`.github/workflows/deploy.yml` publishes the `web/` folder to **GitHub Pages** on
every push to the `Geminis-Go` branch (and via manual `workflow_dispatch`). The
site is fully static, so this is a plain artifact upload — no build step.

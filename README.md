# PT Lernkarten – Anatomy Flashcard System

An interactive anatomy study tool for physiotherapy. Two types of content are supported:

- **Image quizzes** — place labelled anatomy images in `Input/`; the pipeline strips the text and generates a quiz where learners type in the anatomical terms.
- **Text quizzes** — create an Excel or CSV table with questions and answers; the converter generates a structured input quiz with multi-answer support.

---

## Architecture

```
Input/ (labelled images)          Tabellen/ (Excel / CSV)
        │                                  │
        ▼                                  ▼
┌───────────────────┐         ┌────────────────────────┐
│  Python Pipeline  │         │  convert_text.py       │
│  (OCR + Whiteout) │         │  (table → JSON)        │
└───────────────────┘         └────────────────────────┘
        │                                  │
        ▼                                  ▼
   web/data/data.json           web/data/text-data.json
   web/data/images/
        │                                  │
        └──────────────┬───────────────────┘
                       ▼
            ┌─────────────────────┐
            │   Static Web App    │   no backend, no build step
            │   (HTML / CSS / JS) │
            └─────────────────────┘
```

---

## Phase 1a – Image Pipeline (`pipeline/process.py`)

### What it does

1. **OCR** (`ocr.py`) — runs PaddleOCR on each image to find every text label and its bounding box `{x, y, w, h, text}`.
2. **Whiteout** (`inpaint.py`) — paints white rectangles over the detected text.
3. **Export** (`export.py`) — writes `web/data/data.json` and saves clean images to `web/data/images/`.

### File naming convention

```
Fach-Kategorie-Unterkategorie-Ansicht.{jpg,jpeg,png,tif,tiff}
```

Example: `Anatomie 1-Knochen-Arm-dorsal.jpg` → menu entry **Anatomie 1 › Knochen › Arm › dorsal**

### Setup

```bash
# Install PaddlePaddle GPU first (match your CUDA version):
# CUDA 12.3:
pip install paddlepaddle-gpu==3.1.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu123/ --extra-index-url https://pypi.org/simple/
# CUDA 12.6:
pip install paddlepaddle-gpu==3.3.1 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/ --extra-index-url https://pypi.org/simple/

pip install -r pipeline/requirements.txt
```

### Run

```bash
python pipeline/process.py [input_dir] [--output-web <path_to_web/>]
```

- `input_dir` — folder with source images (default: `Input/`).
- `--output-web` — path to the `web/` directory (default: `../web`).

---

## Phase 1b – Text Converter (`pipeline/convert_text.py`)

Converts an Excel or CSV table into `web/data/text-data.json` so text quizzes appear in the same menu as image quizzes.

### Table format

| Name *(first column)* | Kategorie A | Kategorie B | … |
|---|---|---|---|
| Frage / Subjekt | Antwort | Antwort1; Antwort2 | … |

- **Row 1** — column headers. The first column header is the subject label (always visible). All other headers become answer categories shown above the input fields.
- **Row 2+** — one question per row. First cell = question/subject. Other cells = answers, multiple answers separated by `;`.

### File naming convention (same as images)

```
Fach-Kategorie-Unterkategorie-Ansicht.{xlsx,csv}
```

Example: `Anatomie 1-Muskeln Detail-Gesäß-Gluteus.xlsx` → menu entry **Anatomie 1 › Muskeln Detail › Gesäß › Gluteus**

### Run

```bash
python pipeline/convert_text.py "Tabellen/Anatomie 1-Muskeln Detail-Gesäß-Gluteus.xlsx"
```

Running the command again on the same file updates the existing entry (no duplicates).

---

## Phase 2 – Web App (`web/`)

A fully static, client-side application.

### Running locally

```bash
cd web
python3 -m http.server 8080
# open http://localhost:8080
```

### Image quiz

**On topic selection** — `quiz.js` loads the cleaned image and draws a small numbered marker at each label's position (from the `mask_box` coordinates in `data.json`, scaled to the rendered image size). The actual answer fields don't sit on the image — they live in a separate panel, one numbered row per marker, matched by number.

**Layout** — the answer panel sits to the right of the image on wide (landscape) viewports and below the image on tall (portrait) viewports, switching automatically via CSS as the window is resized or the device is rotated. The panel scrolls independently if the rows don't all fit; the image itself always stays fully visible and zoomable.

**Validation** — prefix matching on every keystroke:

| State | Visual |
|---|---|
| Correct (exact, case-insensitive) | Green, field locked |
| Typing in progress (prefix match) | Green gradient |
| No match (wrong) | Orange |

**Help button** (`?`) — one per row in the answer panel, opens a modal showing the correct term.

**Window resize** — marker positions on the image recalculate automatically. The answer panel's layout doesn't depend on image size, so field state (values, colours, locked fields) is untouched.

### Text quiz

**On topic selection** — `quiz.js` renders a scrollable list of question sections. Each section shows the subject name at the top, then one input group per answer category.

**Multi-answer pool logic** — each answer category tracks a pool of remaining correct answers. When a field is answered correctly, that answer is claimed and removed from the pool. Other fields only accept answers still in the pool — in any order.

Example with 3 answers `["A", "B", "C"]`:
- User types "B" in field 1 → B is claimed, pool becomes `[A, C]`.
- Field 2 and 3 now only accept "A" or "C".

**Help button** (`?`, per category) — shows one random answer from the remaining pool. Once all answers are claimed, shows "Alle Antworten korrekt ✓".

---

## Project Structure

```
PT Lernkarten/
├── Input/                      # source images (labelled originals)
├── Tabellen/                   # Excel / CSV quiz tables
├── pipeline/
│   ├── process.py              # image pipeline CLI
│   ├── convert_text.py         # Excel/CSV → text-data.json
│   ├── ocr.py
│   ├── inpaint.py
│   ├── export.py
│   ├── requirements.txt
│   └── tests/
└── web/
    ├── index.html
    ├── css/style.css
    ├── js/
    │   ├── app.js              # bootstrap, fetch, wiring
    │   ├── menu.js             # accordion menu builder
    │   ├── quiz.js             # image + text quiz logic
    │   └── levenshtein.js      # fuzzy matching
    └── data/
        ├── data.json           # generated by process.py
        ├── text-data.json      # generated by convert_text.py
        └── images/             # generated by process.py
```

---

## data.json Format (image quizzes)

```json
[
  {
    "filename": "Knochen-Arm-dorsal-clean.jpg",
    "og_filename": "Knochen-Arm-dorsal.jpg",
    "category": "Knochen",
    "subcategory": "Arm",
    "view": "dorsal",
    "labels": [
      { "text": "Humerus", "anchor_x": 80, "anchor_y": 40,
        "mask_box": { "x": 50, "y": 30, "w": 130, "h": 28 } }
    ]
  }
]
```

## text-data.json Format (text quizzes)

```json
[
  {
    "type": "text",
    "category": "Muskeln Detail",
    "subcategory": "Gesäß",
    "view": "Gluteus",
    "columns": ["Ursprung", "Ansatz", "Funktion", "Innervation"],
    "rows": [
      {
        "question": "M. gluteus maximus",
        "answers": {
          "Ursprung": ["Facies glutea: Os ilium", "Lig. Sacrotuberale"],
          "Ansatz":   ["Tuberositas glutea"],
          "Funktion": ["Extension", "Außenrotation"],
          "Innervation": ["N. gluteus inferior (L5-S2)"]
        }
      }
    ]
  }
]
```

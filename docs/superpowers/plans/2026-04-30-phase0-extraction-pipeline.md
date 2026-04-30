# Phase 0 Extraction Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract anatomical figures from a PDF, classify them with a local VLM, and save them to `Pics/` using the `Kategorie-Unterkategorie-Ansicht.jpg` naming convention so Phase 1 can process them.

**Architecture:** PyMuPDF detects image-block bounding boxes in the born-digital PDF; each qualifying region is rasterized at 300 DPI and passed to Qwen2.5-VL-7B-Instruct which returns a structured JSON classification. The runner orchestrates the loop, saves valid results, and logs everything.

**Tech Stack:** PyMuPDF (fitz), Pillow, transformers + qwen-vl-utils, PyTorch 2.11 (cu126), pytest, Python 3.12

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `pipeline/requirements.txt` | Add 4 new deps |
| Create | `pipeline/pdf_extract.py` | `iter_figures()` — PyMuPDF image detection + 300 DPI rasterization |
| Create | `pipeline/vlm_classify.py` | `classify()` — Qwen2.5-VL singleton + response parsing |
| Create | `pipeline/phase0_runner.py` | `run()` — orchestration loop, file save, RunStats |
| Create | `phase0_extract.py` | CLI entry point, argparse, logging setup |
| Create | `pipeline/tests/test_pdf_extract.py` | Tests for iter_figures |
| Create | `pipeline/tests/test_vlm_classify.py` | Tests for _parse_response + classify (model mocked) |
| Create | `pipeline/tests/test_phase0_runner.py` | Tests for run(), collision, dry_run, RunStats |

---

## Task 1: Update requirements.txt

**Files:**
- Modify: `pipeline/requirements.txt`

- [ ] **Step 1: Add the four new dependencies**

Open `pipeline/requirements.txt` and add these lines (keep existing content):

```
PyMuPDF>=1.24
transformers>=4.49
qwen-vl-utils>=0.0.8
accelerate>=0.27
```

Final file should look like:
```
# Install PaddlePaddle GPU first (match your CUDA version):
# CUDA 11.8: pip install paddlepaddle-gpu==2.6.1.post118 -i https://www.paddlepaddle.org.cn/packages/stable/cu118/
# CUDA 12.3: pip install paddlepaddle-gpu==2.6.2.post120 -i https://www.paddlepaddle.org.cn/packages/stable/cu120/
paddleocr>=2.7.0
# simple-lama-inpainting has a stale pillow<10 pin; install with --no-deps (see below)
# pip install --no-deps simple-lama-inpainting>=0.1.2
Pillow>=10.0
numpy>=1.24
pytest>=7.0
PyMuPDF>=1.24
transformers>=4.49
qwen-vl-utils>=0.0.8
accelerate>=0.27
```

- [ ] **Step 2: Install new deps into the project venv**

```bash
cd "/home/diem/PT Lernkarten"
.venv/bin/pip install "PyMuPDF>=1.24" "transformers>=4.49" "qwen-vl-utils>=0.0.8" "accelerate>=0.27"
```

Expected: all packages install without error. `PyMuPDF` may already be installed from the brainstorming session — that's fine.

- [ ] **Step 3: Commit**

```bash
cd "/home/diem/PT Lernkarten"
git add pipeline/requirements.txt
git commit -m "feat(phase0): add PyMuPDF, transformers, qwen-vl-utils, accelerate deps"
```

---

## Task 2: `pipeline/pdf_extract.py` — PDF Figure Extraction

**Files:**
- Create: `pipeline/pdf_extract.py`
- Create: `pipeline/tests/test_pdf_extract.py`

### Helper — create a minimal test PDF in memory

All tests for this module use this fixture. Add it to `pipeline/tests/test_pdf_extract.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import io
import pytest
import fitz
from PIL import Image
from pdf_extract import iter_figures


def _make_test_pdf(tmp_path, img_pts=(200, 200), n_images=1):
    """Create a single-page PDF with n_images embedded at the given size in points."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    # Create a solid-colour PNG to embed
    pil = Image.new("RGB", (100, 100), color=(128, 64, 32))
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    w_pts, h_pts = img_pts
    for i in range(n_images):
        x0 = 50 + i * (w_pts + 10)
        rect = fitz.Rect(x0, 50, x0 + w_pts, 50 + h_pts)
        page.insert_image(rect, stream=png_bytes)
    pdf_path = tmp_path / "test.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path
```

- [ ] **Step 1: Write the failing tests**

Add these test functions to `pipeline/tests/test_pdf_extract.py`:

```python
def test_yields_pil_image(tmp_path):
    pdf = _make_test_pdf(tmp_path, img_pts=(200, 200))
    results = list(iter_figures(pdf, min_size=50))
    assert len(results) == 1
    page_no, img_idx, img = results[0]
    assert isinstance(img, Image.Image)
    assert page_no == 1


def test_page_no_is_1_indexed(tmp_path):
    pdf = _make_test_pdf(tmp_path, img_pts=(200, 200))
    results = list(iter_figures(pdf, min_size=50))
    assert results[0][0] == 1  # first page is page 1, not page 0


def test_min_size_filters_small_image(tmp_path):
    # 60x60 pt image — should be filtered when min_size=100
    pdf = _make_test_pdf(tmp_path, img_pts=(60, 60))
    results = list(iter_figures(pdf, min_size=100))
    assert results == []


def test_min_size_keeps_qualifying_image(tmp_path):
    pdf = _make_test_pdf(tmp_path, img_pts=(200, 200))
    results = list(iter_figures(pdf, min_size=100))
    assert len(results) == 1


def test_page_range_1indexed(tmp_path):
    # Two-page PDF: image on page 1 only
    doc = fitz.open()
    pil = Image.new("RGB", (100, 100), color=(0, 0, 0))
    buf = io.BytesIO(); pil.save(buf, format="PNG"); png = buf.getvalue()
    p1 = doc.new_page(width=595, height=842)
    p1.insert_image(fitz.Rect(50, 50, 250, 250), stream=png)
    doc.new_page(width=595, height=842)  # empty page 2
    pdf = tmp_path / "two.pdf"; doc.save(str(pdf)); doc.close()

    # page_range=(2,2) should yield nothing (image is on page 1)
    results = list(iter_figures(pdf, min_size=50, page_range=(2, 2)))
    assert results == []

    # page_range=(1,1) should yield one image
    results = list(iter_figures(pdf, min_size=50, page_range=(1, 1)))
    assert len(results) == 1


def test_skips_and_continues_on_error(tmp_path, caplog):
    """A bad page must not crash the generator."""
    import logging
    pdf = _make_test_pdf(tmp_path, img_pts=(200, 200))

    original_iter = iter_figures.__wrapped__ if hasattr(iter_figures, '__wrapped__') else None

    with caplog.at_level(logging.ERROR, logger="pdf_extract"):
        # Patch get_pixmap to raise on the first call, succeed on nothing (single image)
        import fitz as _fitz
        original_open = _fitz.open

        class _BadPage:
            def get_image_info(self, xrefs=True):
                return [{"bbox": (50, 50, 250, 250), "xref": 1}]
            def get_pixmap(self, **kwargs):
                raise RuntimeError("simulated raster failure")

        class _BadDoc:
            page_count = 1
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def close(self): pass
            def load_page(self, i): return _BadPage()
            def __getitem__(self, i): return _BadPage()
            def __iter__(self): yield _BadPage()

        import unittest.mock as mock
        with mock.patch("fitz.open", return_value=_BadDoc()):
            results = list(iter_figures(pdf, min_size=50))

    assert results == []
    assert any("ERROR" in r.levelname or r.levelno >= logging.ERROR for r in caplog.records)
```

- [ ] **Step 2: Run tests — expect failures**

```bash
cd "/home/diem/PT Lernkarten"
.venv/bin/pytest pipeline/tests/test_pdf_extract.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'pdf_extract'`

- [ ] **Step 3: Implement `pipeline/pdf_extract.py`**

```python
import logging
from pathlib import Path
from typing import Iterator

import fitz
from PIL import Image

log = logging.getLogger("pdf_extract")


def iter_figures(
    pdf_path: str | Path,
    min_size: int = 150,
    page_range: tuple[int, int] | None = None,
) -> Iterator[tuple[int, int, Image.Image]]:
    """Yield (page_no, img_index, PIL.Image) for each qualifying figure in the PDF.

    page_no is 1-indexed. min_size is in PDF points (72 pt = 1 inch).
    page_range is (start, end) 1-indexed inclusive; None means all pages.
    """
    pdf_path = Path(pdf_path)
    doc = fitz.open(str(pdf_path))
    try:
        total_pages = doc.page_count
        if page_range is not None:
            start = max(1, page_range[0]) - 1   # convert to 0-indexed
            end = min(total_pages, page_range[1]) - 1
        else:
            start, end = 0, total_pages - 1

        for page_idx in range(start, end + 1):
            page_no = page_idx + 1  # 1-indexed for logging
            try:
                page = doc[page_idx]
                infos = page.get_image_info(xrefs=True)
                for img_idx, info in enumerate(infos):
                    try:
                        x0, y0, x1, y1 = info["bbox"]
                        w_pts = x1 - x0
                        h_pts = y1 - y0
                        if w_pts < min_size or h_pts < min_size:
                            log.debug(
                                "p%d img%d discarded: too small (%.0f×%.0f pts)",
                                page_no, img_idx, w_pts, h_pts,
                            )
                            continue
                        rect = fitz.Rect(x0, y0, x1, y1)
                        pix = page.get_pixmap(clip=rect, dpi=300)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        yield page_no, img_idx, img
                    except Exception as exc:
                        log.error("p%d img%d error: %s", page_no, img_idx, exc)
            except Exception as exc:
                log.error("page %d error: %s", page_no, exc)
    finally:
        doc.close()
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
cd "/home/diem/PT Lernkarten"
.venv/bin/pytest pipeline/tests/test_pdf_extract.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "/home/diem/PT Lernkarten"
git add pipeline/pdf_extract.py pipeline/tests/test_pdf_extract.py
git commit -m "feat(phase0): add pdf_extract.iter_figures with tests"
```

---

## Task 3: `pipeline/vlm_classify.py` — VLM Classification

**Files:**
- Create: `pipeline/vlm_classify.py`
- Create: `pipeline/tests/test_vlm_classify.py`

The module has two layers:
- `_parse_response(text: str) -> tuple[dict|None, str]` — pure function, fully testable without the model
- `classify(image) -> tuple[dict|None, str]` — calls the model + delegates to `_parse_response`

- [ ] **Step 1: Write the failing tests**

Create `pipeline/tests/test_vlm_classify.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image
from vlm_classify import _parse_response, classify


# ── _parse_response tests (pure, no model) ────────────────────────────────────

def test_parse_garbage_text():
    result, reason = _parse_response("not json at all")
    assert result is None
    assert reason == "json parse failure"


def test_parse_no_braces():
    result, reason = _parse_response("hello world")
    assert result is None
    assert reason == "json parse failure"


def test_parse_is_anatomical_false_bool():
    text = json.dumps({"is_anatomical": False, "category": "Knochen",
                        "subcategory": "Arm", "view": "dorsal"})
    result, reason = _parse_response(text)
    assert result is None
    assert reason == "not anatomical"


def test_parse_is_anatomical_string_false():
    text = json.dumps({"is_anatomical": "false", "category": "Knochen",
                        "subcategory": "Arm", "view": "dorsal"})
    result, reason = _parse_response(text)
    assert result is None
    assert reason == "not anatomical"


def test_parse_is_anatomical_string_true_accepted():
    text = json.dumps({"is_anatomical": "true", "category": "Knochen",
                        "subcategory": "Arm", "view": "dorsal"})
    result, reason = _parse_response(text)
    assert result is not None
    assert reason == ""


def test_parse_is_anatomical_string_True_accepted():
    text = json.dumps({"is_anatomical": "True", "category": "Muskeln",
                        "subcategory": "Bein", "view": "lateral"})
    result, reason = _parse_response(text)
    assert result is not None


def test_parse_missing_is_anatomical_key():
    text = json.dumps({"category": "Knochen", "subcategory": "Arm", "view": "dorsal"})
    result, reason = _parse_response(text)
    assert result is None
    assert reason == "missing field: is_anatomical"


def test_parse_missing_category():
    text = json.dumps({"is_anatomical": True, "subcategory": "Arm", "view": "dorsal"})
    result, reason = _parse_response(text)
    assert result is None
    assert "category" in reason


def test_parse_missing_view():
    text = json.dumps({"is_anatomical": True, "category": "Knochen",
                        "subcategory": "Arm", "view": ""})
    result, reason = _parse_response(text)
    assert result is None
    assert "view" in reason


def test_parse_unknown_category():
    text = json.dumps({"is_anatomical": True, "category": "Wirbelsäule",
                        "subcategory": "Arm", "view": "dorsal"})
    result, reason = _parse_response(text)
    assert result is None
    # implementation returns "unknown category: Wirbelsäule" (untransliterated)
    assert reason.startswith("unknown category:")


def test_parse_umlaut_transliteration():
    text = json.dumps({"is_anatomical": True, "category": "Bänder",
                        "subcategory": "Fuß", "view": "lateral"})
    result, reason = _parse_response(text)
    assert result is not None
    assert result["category"] == "Baender"
    assert result["subcategory"] == "Fuss"
    assert result["view"] == "lateral"


def test_parse_view_lowercased():
    text = json.dumps({"is_anatomical": True, "category": "Knochen",
                        "subcategory": "Arm", "view": "Dorsal"})
    result, _ = _parse_response(text)
    assert result["view"] == "dorsal"


def test_parse_category_title_cased():
    text = json.dumps({"is_anatomical": True, "category": "knochen",
                        "subcategory": "arm", "view": "dorsal"})
    result, _ = _parse_response(text)
    assert result is not None  # "knochen".title() == "Knochen" which is valid enum


def test_parse_spaces_replaced_with_underscores():
    text = json.dumps({"is_anatomical": True, "category": "Knochen",
                        "subcategory": "Hand Finger", "view": "dorsal"})
    result, _ = _parse_response(text)
    assert result is not None
    assert " " not in result["subcategory"]
    assert result["subcategory"] == "Hand_Finger"


def test_parse_json_embedded_in_prose():
    """VLM sometimes wraps JSON in explanation text."""
    prose = 'Here is the result: {"is_anatomical": true, "category": "Knochen", "subcategory": "Arm", "view": "dorsal"} Hope that helps!'
    result, reason = _parse_response(prose)
    assert result is not None


# ── classify() tests (model mocked) ──────────────────────────────────────────

def _dummy_image():
    return Image.new("RGB", (64, 64), color=(128, 128, 128))


def test_classify_returns_dict_on_valid_response():
    valid_json = json.dumps({"is_anatomical": True, "category": "Knochen",
                              "subcategory": "Arm", "view": "dorsal"})
    with patch("vlm_classify._generate_response", return_value=valid_json):
        result, reason = classify(_dummy_image())
    assert result == {"category": "Knochen", "subcategory": "Arm", "view": "dorsal"}
    assert reason == ""


def test_classify_returns_none_on_not_anatomical():
    not_anat = json.dumps({"is_anatomical": False, "category": None,
                            "subcategory": None, "view": None})
    with patch("vlm_classify._generate_response", return_value=not_anat):
        result, reason = classify(_dummy_image())
    assert result is None
    assert reason == "not anatomical"


def test_classify_returns_none_on_model_exception():
    with patch("vlm_classify._generate_response", side_effect=RuntimeError("GPU OOM")):
        result, reason = classify(_dummy_image())
    assert result is None
    assert "GPU OOM" in reason or "error" in reason.lower()
```

- [ ] **Step 2: Run tests — expect failures**

```bash
cd "/home/diem/PT Lernkarten"
.venv/bin/pytest pipeline/tests/test_vlm_classify.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'vlm_classify'`

- [ ] **Step 3: Implement `pipeline/vlm_classify.py`**

```python
import json
import logging
import re
from pathlib import Path
from typing import Any

from PIL import Image

log = logging.getLogger("vlm_classify")

_UMLAUT_MAP = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
})

_VALID_CATEGORIES = {
    "Knochen", "Muskeln", "Gelenke", "Bänder", "Gefäße", "Nerven", "Organe"
}

_SYSTEM_PROMPT = (
    "You are an anatomy atlas classifier. "
    "Respond ONLY with a JSON object — no prose, no markdown fences."
)

_USER_PROMPT = (
    "Look at this image. Return a JSON object with these keys:\n"
    "- is_anatomical (bool): true if this is an anatomical diagram containing pointer lines or labels\n"
    "- category (str or null): one of Knochen, Muskeln, Gelenke, Bänder, Gefäße, Nerven, Organe\n"
    "- subcategory (str or null): e.g. Arm, Bein, Kopf, Rumpf, Becken, Hand, Fuß, Schulter, Hüfte\n"
    "- view (str or null): e.g. dorsal, ventral, lateral, medial, frontal, superior, inferior\n"
    "If is_anatomical is false, set the other fields to null."
)

_model = None
_processor = None


def _load_model() -> None:
    global _model, _processor
    if _model is not None:
        return
    import torch
    from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor

    log.info("Loading Qwen2.5-VL-7B-Instruct …")
    model_id = "Qwen/Qwen2.5-VL-7B-Instruct"
    _processor = AutoProcessor.from_pretrained(model_id)
    _model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        device_map="cuda",
    )
    _model.eval()
    log.info("Model loaded.")


def _generate_response(image: Image.Image) -> str:
    """Run inference and return the raw text response."""
    _load_model()
    from qwen_vl_utils import process_vision_info

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": _USER_PROMPT},
            ],
        },
    ]
    text = _processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = _processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    ).to(_model.device)

    import torch
    with torch.no_grad():
        output_ids = _model.generate(**inputs, max_new_tokens=256)
    trimmed = output_ids[:, inputs["input_ids"].shape[1]:]
    return _processor.batch_decode(trimmed, skip_special_tokens=True)[0]


def _parse_response(text: str) -> tuple[dict | None, str]:
    """Parse VLM text → (classification_dict, reason). reason is '' on success."""
    # Step 1-2: extract and parse JSON
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None, "json parse failure"
    try:
        data: dict[str, Any] = json.loads(match.group())
    except json.JSONDecodeError:
        return None, "json parse failure"

    # Step 3: is_anatomical
    if "is_anatomical" not in data:
        return None, "missing field: is_anatomical"
    val = data["is_anatomical"]
    if val is not True and str(val) not in ("true", "True"):
        return None, "not anatomical"

    # Step 4: required fields present and non-empty
    for field in ("category", "subcategory", "view"):
        if not data.get(field):
            return None, f"missing field: {field}"

    # Step 5: normalise — strip, title-case cat/sub, lowercase view
    category = data["category"].strip().title()
    subcategory = data["subcategory"].strip().title()
    view = data["view"].strip().lower()

    # Step 6: validate category (after title-case, before transliteration)
    if category not in _VALID_CATEGORIES:
        return None, f"unknown category: {category}"

    # Step 7: transliterate Umlauts, replace spaces
    category = category.translate(_UMLAUT_MAP).replace(" ", "_")
    subcategory = subcategory.translate(_UMLAUT_MAP).replace(" ", "_")
    view = view.translate(_UMLAUT_MAP).replace(" ", "_")

    return {"category": category, "subcategory": subcategory, "view": view}, ""


def classify(image: Image.Image) -> tuple[dict | None, str]:
    """
    Returns (result, reason).
    result is {"category": str, "subcategory": str, "view": str} on success, else None.
    reason is "" when result is not None.
    """
    try:
        raw = _generate_response(image)
        return _parse_response(raw)
    except Exception as exc:
        return None, f"model error: {exc}"
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
cd "/home/diem/PT Lernkarten"
.venv/bin/pytest pipeline/tests/test_vlm_classify.py -v
```

Expected: all 18 tests PASS. (No GPU required — model calls are mocked.)

- [ ] **Step 5: Commit**

```bash
cd "/home/diem/PT Lernkarten"
git add pipeline/vlm_classify.py pipeline/tests/test_vlm_classify.py
git commit -m "feat(phase0): add vlm_classify with parse/sanitise logic and tests"
```

---

## Task 4: `pipeline/phase0_runner.py` — Orchestration Loop

**Files:**
- Create: `pipeline/phase0_runner.py`
- Create: `pipeline/tests/test_phase0_runner.py`

- [ ] **Step 1: Write the failing tests**

Create `pipeline/tests/test_phase0_runner.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image
from phase0_runner import run, RunStats


def _dummy_image():
    return Image.new("RGB", (64, 64))


def _make_figure(page=1, idx=0):
    return (page, idx, _dummy_image())


GOOD_CLASS = ({"category": "Knochen", "subcategory": "Arm", "view": "dorsal"}, "")
DISCARD_CLASS = (None, "not anatomical")


def test_run_saves_file(tmp_path):
    with patch("phase0_runner.iter_figures", return_value=[_make_figure()]), \
         patch("phase0_runner.classify", return_value=GOOD_CLASS):
        stats = run("fake.pdf", tmp_path)
    assert stats.saved == 1
    assert (tmp_path / "Knochen-Arm-dorsal.jpg").exists()


def test_run_dry_run_does_not_save(tmp_path):
    with patch("phase0_runner.iter_figures", return_value=[_make_figure()]), \
         patch("phase0_runner.classify", return_value=GOOD_CLASS):
        stats = run("fake.pdf", tmp_path, dry_run=True)
    assert stats.saved == 0
    assert not (tmp_path / "Knochen-Arm-dorsal.jpg").exists()


def test_run_discarded_incremented(tmp_path):
    with patch("phase0_runner.iter_figures", return_value=[_make_figure()]), \
         patch("phase0_runner.classify", return_value=DISCARD_CLASS):
        stats = run("fake.pdf", tmp_path)
    assert stats.discarded == 1
    assert stats.saved == 0


def test_run_collision_suffix(tmp_path):
    figures = [_make_figure(page=1), _make_figure(page=2)]
    with patch("phase0_runner.iter_figures", return_value=figures), \
         patch("phase0_runner.classify", return_value=GOOD_CLASS):
        stats = run("fake.pdf", tmp_path)
    assert stats.saved == 2
    assert (tmp_path / "Knochen-Arm-dorsal.jpg").exists()
    assert (tmp_path / "Knochen-Arm-dorsal_2.jpg").exists()


def test_run_collision_three(tmp_path):
    figures = [_make_figure(page=i) for i in range(3)]
    with patch("phase0_runner.iter_figures", return_value=figures), \
         patch("phase0_runner.classify", return_value=GOOD_CLASS):
        stats = run("fake.pdf", tmp_path)
    assert stats.saved == 3
    assert (tmp_path / "Knochen-Arm-dorsal_3.jpg").exists()


def test_run_error_handling(tmp_path):
    """Exception inside classify must increment errors and continue."""
    with patch("phase0_runner.iter_figures", return_value=[_make_figure()]), \
         patch("phase0_runner.classify", side_effect=RuntimeError("boom")):
        stats = run("fake.pdf", tmp_path)
    assert stats.errors == 1
    assert stats.saved == 0


def test_run_error_counts_once_per_image(tmp_path):
    """Even if multiple things fail per image, errors increments by 1."""
    with patch("phase0_runner.iter_figures", return_value=[_make_figure()]), \
         patch("phase0_runner.classify", side_effect=RuntimeError("boom")):
        stats = run("fake.pdf", tmp_path)
    assert stats.errors == 1


def test_run_total_counts_all_figures(tmp_path):
    figures = [_make_figure(i) for i in range(5)]
    classify_results = [GOOD_CLASS, GOOD_CLASS, DISCARD_CLASS, DISCARD_CLASS, GOOD_CLASS]
    with patch("phase0_runner.iter_figures", return_value=figures), \
         patch("phase0_runner.classify", side_effect=classify_results):
        stats = run("fake.pdf", tmp_path)
    assert stats.total == 5
    assert stats.saved == 3
    assert stats.discarded == 2
    assert stats.errors == 0


def test_run_creates_output_dir(tmp_path):
    out = tmp_path / "new" / "nested"
    with patch("phase0_runner.iter_figures", return_value=[]), \
         patch("phase0_runner.classify", return_value=GOOD_CLASS):
        run("fake.pdf", out)
    assert out.is_dir()
```

- [ ] **Step 2: Run tests — expect failures**

```bash
cd "/home/diem/PT Lernkarten"
.venv/bin/pytest pipeline/tests/test_phase0_runner.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'phase0_runner'`

- [ ] **Step 3: Implement `pipeline/phase0_runner.py`**

```python
import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from pdf_extract import iter_figures
from vlm_classify import classify

log = logging.getLogger("phase0_runner")


@dataclass
class RunStats:
    total: int = 0
    saved: int = 0
    discarded: int = 0
    errors: int = 0


def _resolve_output_path(output_dir: Path, stem: str) -> Path:
    """Return a non-colliding path: stem.jpg, stem_2.jpg, stem_3.jpg …"""
    candidate = output_dir / f"{stem}.jpg"
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = output_dir / f"{stem}_{n}.jpg"
        if not candidate.exists():
            return candidate
        n += 1


def run(
    pdf_path: str | Path,
    output_dir: str | Path,
    min_size: int = 150,
    page_range: tuple[int, int] | None = None,
    dry_run: bool = False,
) -> RunStats:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stats = RunStats()

    for page_no, img_idx, image in iter_figures(pdf_path, min_size=min_size, page_range=page_range):
        stats.total += 1
        try:
            result, reason = classify(image)
            if result is None:
                log.debug("p%d img%d discarded: %s", page_no, img_idx, reason)
                stats.discarded += 1
                continue

            stem = f"{result['category']}-{result['subcategory']}-{result['view']}"
            out_path = _resolve_output_path(output_dir, stem)

            if dry_run:
                log.info("[dry-run] would save → %s", out_path.name)
            else:
                image.save(out_path, "JPEG", quality=95)
                log.info("saved → %s", out_path.name)
                stats.saved += 1

        except Exception as exc:
            log.error("p%d img%d error: %s", page_no, img_idx, exc)
            stats.errors += 1

    return stats
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
cd "/home/diem/PT Lernkarten"
.venv/bin/pytest pipeline/tests/test_phase0_runner.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "/home/diem/PT Lernkarten"
git add pipeline/phase0_runner.py pipeline/tests/test_phase0_runner.py
git commit -m "feat(phase0): add phase0_runner orchestration loop with tests"
```

---

## Task 5: `phase0_extract.py` — CLI Entry Point

**Files:**
- Create: `phase0_extract.py` (at project root, NOT inside pipeline/)

- [ ] **Step 1: Write tests**

Add `pipeline/tests/test_phase0_extract.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import phase0_extract
from phase0_extract import _parse_pages_arg, _find_default_pdf


def test_parse_pages_arg_valid():
    assert _parse_pages_arg("1-100") == (1, 100)
    assert _parse_pages_arg("5-5") == (5, 5)
    assert _parse_pages_arg("10-200") == (10, 200)


def test_parse_pages_arg_invalid():
    with pytest.raises(ValueError):
        _parse_pages_arg("abc")
    with pytest.raises(ValueError):
        _parse_pages_arg("100")
    with pytest.raises(ValueError):
        _parse_pages_arg("5-3")   # end < start


def test_find_default_pdf(tmp_path):
    (tmp_path / "atlas.pdf").write_bytes(b"%PDF")
    (tmp_path / "notes.txt").write_bytes(b"text")
    result = _find_default_pdf(tmp_path)
    assert result == tmp_path / "atlas.pdf"


def test_find_default_pdf_none(tmp_path):
    result = _find_default_pdf(tmp_path)
    assert result is None


def test_main_exits_1_when_pdf_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "phase0_extract.py",
        "--input", str(tmp_path / "nonexistent.pdf"),
        "--output", str(tmp_path),
    ])
    with pytest.raises(SystemExit) as exc:
        phase0_extract.main()
    assert exc.value.code == 1


def test_main_calls_run(tmp_path, monkeypatch):
    fake_pdf = tmp_path / "atlas.pdf"
    fake_pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(sys, "argv", [
        "phase0_extract.py",
        "--input", str(fake_pdf),
        "--output", str(tmp_path),
        "--dry-run",
    ])
    from phase0_runner import RunStats
    mock_run = MagicMock(return_value=RunStats(total=10, saved=3, discarded=7, errors=0))
    with patch("phase0_extract.run", mock_run):
        phase0_extract.main()
    mock_run.assert_called_once()
    call_kwargs = mock_run.call_args
    assert call_kwargs.kwargs.get("dry_run") is True or call_kwargs.args[4] is True
```

- [ ] **Step 2: Run tests — expect failures**

```bash
cd "/home/diem/PT Lernkarten"
.venv/bin/pytest pipeline/tests/test_phase0_extract.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'phase0_extract'`

- [ ] **Step 3: Implement `phase0_extract.py`**

```python
#!/usr/bin/env python3
"""Phase 0: Extract and classify anatomical figures from a PDF."""
import argparse
import logging
import sys
from pathlib import Path

# pipeline/ is next to this file
sys.path.insert(0, str(Path(__file__).parent / "pipeline"))

from phase0_runner import run

_PROJECT_ROOT = Path(__file__).parent
_LOG_FILE = _PROJECT_ROOT / "pipeline.log"


def _setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    root.addHandler(ch)
    root.addHandler(fh)


def _parse_pages_arg(value: str) -> tuple[int, int]:
    parts = value.split("-")
    if len(parts) != 2:
        raise ValueError(f"--pages must be START-END, got {value!r}")
    start, end = int(parts[0]), int(parts[1])
    if end < start:
        raise ValueError(f"--pages end ({end}) must be >= start ({start})")
    return start, end


def _find_default_pdf(buch_dir: Path) -> Path | None:
    pdfs = sorted(buch_dir.glob("*.pdf"))
    return pdfs[0] if pdfs else None


def main() -> None:
    _setup_logging()
    log = logging.getLogger("phase0")

    parser = argparse.ArgumentParser(description="Phase 0: PDF → Pics extraction")
    parser.add_argument("--input", type=Path, default=None,
                        help="Path to PDF (default: first PDF in Buch/)")
    parser.add_argument("--output", type=Path, default=_PROJECT_ROOT / "Pics",
                        help="Output directory (default: Pics/)")
    parser.add_argument("--min-size", type=int, default=150,
                        help="Minimum image dimension in PDF points (default: 150)")
    parser.add_argument("--pages", type=str, default=None,
                        help="Page range START-END (1-indexed, inclusive)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Classify but do not write files")
    args = parser.parse_args()

    # Resolve PDF path
    pdf_path = args.input
    if pdf_path is None:
        pdf_path = _find_default_pdf(_PROJECT_ROOT / "Buch")
        if pdf_path is None:
            log.error("No PDF found in Buch/ and --input not provided.")
            sys.exit(1)

    if not pdf_path.is_file():
        log.error("PDF not found: %s", pdf_path)
        sys.exit(1)

    # Parse page range
    page_range = None
    if args.pages:
        try:
            page_range = _parse_pages_arg(args.pages)
        except ValueError as exc:
            log.error("Invalid --pages argument: %s", exc)
            sys.exit(1)

    log.info("Phase 0 start | pdf=%s | output=%s | min_size=%d | pages=%s | dry_run=%s",
             pdf_path, args.output, args.min_size, args.pages or "all", args.dry_run)

    stats = run(
        pdf_path=pdf_path,
        output_dir=args.output,
        min_size=args.min_size,
        page_range=page_range,
        dry_run=args.dry_run,
    )

    log.info(
        "Phase 0 complete | total=%d saved=%d discarded=%d errors=%d",
        stats.total, stats.saved, stats.discarded, stats.errors,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
cd "/home/diem/PT Lernkarten"
.venv/bin/pytest pipeline/tests/test_phase0_extract.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Run the full test suite to catch regressions**

```bash
cd "/home/diem/PT Lernkarten"
.venv/bin/pytest pipeline/tests/ -v
```

Expected: all tests pass (existing + new).

- [ ] **Step 6: Commit**

```bash
cd "/home/diem/PT Lernkarten"
git add phase0_extract.py pipeline/tests/test_phase0_extract.py
git commit -m "feat(phase0): add CLI entry point with logging, argparse, and tests"
```

---

## Task 6: Model Pre-Download

Download the VLM weights before running the pipeline. This is a one-time step (~14 GB).

- [ ] **Step 1: Verify GPU is available**

```bash
cd "/home/diem/PT Lernkarten"
.venv/bin/python -c "import torch; print(torch.cuda.get_device_name(0)); print(torch.cuda.get_device_properties(0).total_memory // 1024**3, 'GB')"
```

Expected: `NVIDIA GeForce RTX 3090 Ti` and `24 GB`.

- [ ] **Step 2: Download model weights (one-time, ~14 GB)**

```bash
cd "/home/diem/PT Lernkarten"
.venv/bin/python -c "
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
AutoProcessor.from_pretrained('Qwen/Qwen2.5-VL-7B-Instruct')
print('Processor OK')
Qwen2_5_VLForConditionalGeneration.from_pretrained('Qwen/Qwen2.5-VL-7B-Instruct', torch_dtype='auto')
print('Model OK')
"
```

Expected: progress bars for ~14 GB download on first run, then `Processor OK` and `Model OK`.

---

## Task 7: Smoke Test — Dry Run on Real PDF

Run the full pipeline (including VLM) against a small page slice with `--dry-run` so no files are written to disk.

- [ ] **Step 1: Dry-run on pages 100-110**

```bash
cd "/home/diem/PT Lernkarten"
.venv/bin/python phase0_extract.py \
  --pages 100-110 \
  --dry-run \
  2>&1 | tee /tmp/phase0_smoke.log
```

Expected console output (INFO level only — DEBUG lines appear in `pipeline.log` only):
```
... INFO phase0: Phase 0 start | pdf=Buch/PROMETHEUS... | pages=100-110 | dry_run=True
... INFO phase0: Loading Qwen2.5-VL-7B-Instruct ...
... INFO phase0: Model loaded.
... INFO phase0_runner: [dry-run] would save → Knochen-Arm-dorsal.jpg
... INFO phase0: Phase 0 complete | total=N saved=0 discarded=K errors=0
```

No `ERROR` lines should appear. If they do, check `pipeline.log` for the full traceback.

Note: `saved=0` is expected in dry_run — the stat only counts files actually written to disk.

- [ ] **Step 2: Verify pipeline.log contains DEBUG entries**

```bash
ls -lh "/home/diem/PT Lernkarten/pipeline.log"
grep "discarded" "/home/diem/PT Lernkarten/pipeline.log" | head -5
```

Expected: file exists; DEBUG lines show discarded-too-small images with point dimensions.

- [ ] **Step 3: Add pipeline.log to .gitignore**

```bash
cd "/home/diem/PT Lernkarten"
grep -q "pipeline.log" .gitignore || echo "pipeline.log" >> .gitignore
git add .gitignore
git commit -m "chore: ignore pipeline.log"
```

---

## Task 8: Full Run

Runs the complete pipeline over all 646 pages. Expect ~1–4 hours depending on figure count.

- [ ] **Step 1: Verify process.py accepts the expected arguments before starting**

```bash
cd "/home/diem/PT Lernkarten"
.venv/bin/python pipeline/process.py --help
```

Expected: shows `input_dir` positional arg and `--output-web` option.

- [ ] **Step 2: Run the full pipeline in background**

```bash
cd "/home/diem/PT Lernkarten"
nohup .venv/bin/python phase0_extract.py \
  --output Pics/ \
  >> phase0_run.log 2>&1 &
echo "PID: $!"
```

Monitor progress:
```bash
tail -f "/home/diem/PT Lernkarten/pipeline.log"
```

- [ ] **Step 3: Verify output after completion**

```bash
ls "/home/diem/PT Lernkarten/Pics/" | head -20
ls "/home/diem/PT Lernkarten/Pics/" | wc -l
```

Expected: files named `Knochen-Arm-dorsal.jpg` etc.

- [ ] **Step 4: Feed output into Phase 1**

```bash
cd "/home/diem/PT Lernkarten"
.venv/bin/python pipeline/process.py Pics/ --output-web web/
```

Expected: `data.json` updated, clean images written to `web/data/images/`.

---

## Installation Summary

```bash
cd "/home/diem/PT Lernkarten"

# Install new deps
.venv/bin/pip install "PyMuPDF>=1.24" "transformers>=4.49" "qwen-vl-utils>=0.0.8" "accelerate>=0.27"

# Run all tests
.venv/bin/pytest pipeline/tests/ -v

# Dry-run smoke test (no model needed)
.venv/bin/python phase0_extract.py --pages 100-110 --dry-run

# Full run (downloads ~14 GB model on first run)
.venv/bin/python phase0_extract.py --output Pics/
```

# Pipeline Refactor: Filename Metadata + VLM Sanity Checks + Exact Anchors

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace VLM-based metadata classification with filename parsing, upgrade `detect_labels` to return sanity-check fields (invalid OCR IDs + missing-words flag), and compute exact UI anchor points from OCR coordinates instead of estimations.

**Architecture:** Four sequential tasks, each TDD. (1) Write new failing tests for `vlm_classify`. (2) Refactor `vlm_classify.py` — remove `classify()` and related code, update prompts, change `detect_labels` return type to a dict with groupings + sanity fields. (3) Write + fix `export.py` — new `build_entry` signature with metadata and new label schema. (4) Refactor `process.py` orchestration — filename parsing, marked image creation, sanity-check handling, anchor calculation. No new files; existing test files are updated in place.

**Tech Stack:** Python 3.11+, Pillow (ImageDraw for red-box marking), Qwen2.5-VL-7B-Instruct (via `transformers`/`qwen_vl_utils`), PaddleOCR, pytest

---

## File Map

| File | Status | Responsibility after refactor |
|------|--------|-------------------------------|
| `pipeline/vlm_classify.py` | Modify | VLM inference only: group OCR blocks, detect invalid IDs, flag missing words |
| `pipeline/process.py` | Modify | Orchestration: filename→metadata, create marked image, filter invalid blocks, compute anchors |
| `pipeline/export.py` | Modify | Serialize entries; `build_entry` now accepts metadata kwargs and new label schema |
| `pipeline/tests/test_vlm_classify.py` | Modify | Remove stale tests; add tests for new `detect_labels` contract and `_parse_detection_response` |
| `pipeline/tests/test_export.py` | Modify | Replace `test_build_entry_structure` (old signature); keep `save_data_json` tests |
| `pipeline/tests/test_process.py` | Create | Unit tests for `_parse_stem` helper |

---

## What Gets Removed

From `vlm_classify.py`:
- `_UMLAUT_MAP` — only used by `classify()`
- `_VALID_CATEGORIES` — only used by `classify()`
- `_USER_PROMPT` — only used by `_generate_response()` / `classify()`
- `from typing import Any` import — only used by `_parse_response()`
- `_generate_response()` — only called by `classify()`
- `_parse_response()` — only called by `classify()`
- `classify()` — replaced by filename parsing in `process.py`
- `_parse_json_tolerant()` — only called by `_parse_groupings()`
- `_parse_groupings()` — replaced by `_parse_detection_response()`

From `tests/test_vlm_classify.py`:
- All `_parse_response` tests
- All `classify()` tests
- All `_parse_groupings()` tests (the function is renamed/replaced)

---

### Task 1: Update `test_vlm_classify.py` with new failing tests

**Files:**
- Modify: `pipeline/tests/test_vlm_classify.py`

- [ ] **Step 1: Replace the test file content**

The new file imports only what will exist after the refactor. It keeps the existing `_make_vlm_mock` helper (updated for the new JSON format), removes all tests for removed functions, and adds tests for the new `detect_labels` return contract and the new `_parse_detection_response` helper.

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image
from vlm_classify import detect_labels, _parse_detection_response


# ── _parse_detection_response() tests (pure, no model) ───────────────────────

def test_parse_detection_valid_response():
    raw = json.dumps({
        "groupings": [{"term": "Os sacrum", "ocr_ids": [0, 1]}],
        "invalid_ocr_ids": [2],
        "missing_words_detected": False,
    })
    result = _parse_detection_response(raw)
    assert result["groupings"] == [{"term": "Os sacrum", "ocr_ids": [0, 1]}]
    assert result["invalid_ocr_ids"] == [2]
    assert result["missing_words_detected"] is False


def test_parse_detection_missing_words_true():
    raw = json.dumps({
        "groupings": [],
        "invalid_ocr_ids": [],
        "missing_words_detected": True,
    })
    result = _parse_detection_response(raw)
    assert result["missing_words_detected"] is True


def test_parse_detection_empty_sanity_fields_default_to_safe_values():
    raw = json.dumps({"groupings": [{"term": "Promontorium", "ocr_ids": [0]}]})
    result = _parse_detection_response(raw)
    assert result["invalid_ocr_ids"] == []
    assert result["missing_words_detected"] is False


def test_parse_detection_invalid_json_returns_empty():
    result = _parse_detection_response("not json at all")
    assert result["groupings"] == []
    assert result["invalid_ocr_ids"] == []
    assert result["missing_words_detected"] is False


def test_parse_detection_no_braces_returns_empty():
    result = _parse_detection_response("[1, 2, 3]")
    assert result == {"groupings": [], "invalid_ocr_ids": [], "missing_words_detected": False}


def test_parse_detection_strips_prose_wrapper():
    raw = 'Here is the result: ' + json.dumps({
        "groupings": [{"term": "Basis ossis sacri", "ocr_ids": [1, 2, 3]}],
        "invalid_ocr_ids": [],
        "missing_words_detected": False,
    }) + ' Done.'
    result = _parse_detection_response(raw)
    assert result["groupings"][0]["term"] == "Basis ossis sacri"


def test_parse_detection_strips_term_whitespace():
    raw = json.dumps({
        "groupings": [{"term": "  Os sacrum  ", "ocr_ids": [0]}],
        "invalid_ocr_ids": [],
        "missing_words_detected": False,
    })
    result = _parse_detection_response(raw)
    assert result["groupings"][0]["term"] == "Os sacrum"


def test_parse_detection_skips_malformed_grouping_entries():
    raw = json.dumps({
        "groupings": [
            {"term": "Valid", "ocr_ids": [0]},
            {"no_term": "bad"},
            {"term": "Also valid", "ocr_ids": [1]},
        ],
        "invalid_ocr_ids": [],
        "missing_words_detected": False,
    })
    result = _parse_detection_response(raw)
    assert len(result["groupings"]) == 2
    assert result["groupings"][0]["term"] == "Valid"
    assert result["groupings"][1]["term"] == "Also valid"


# ── detect_labels() integration tests (model mocked) ─────────────────────────

def _dummy_image():
    return Image.new("RGB", (800, 600), color=(200, 200, 200))


def _make_vlm_mock(raw_json: str):
    mock_proc = MagicMock()
    mock_proc.apply_chat_template.return_value = "tmpl"
    mock_inputs = MagicMock()
    mock_inputs.to.return_value = mock_inputs
    mock_inputs.__getitem__ = MagicMock(return_value=MagicMock(shape=[1, 10]))
    mock_proc.return_value = mock_inputs
    mock_proc.batch_decode.return_value = [raw_json]

    mock_model = MagicMock()
    mock_model.device = "cpu"

    mock_qwen = MagicMock()
    mock_qwen.process_vision_info.return_value = ([MagicMock()], None)

    mock_torch = MagicMock()
    mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
    mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=False)

    return mock_proc, mock_model, mock_qwen, mock_torch


def test_detect_labels_returns_dict_with_all_keys():
    ocr_blocks = [{"id": 0, "text": "Humerus", "x": 10, "y": 10, "w": 50, "h": 20}]
    raw_json = json.dumps({
        "groupings": [{"term": "Humerus", "ocr_ids": [0]}],
        "invalid_ocr_ids": [],
        "missing_words_detected": False,
    })
    mock_proc, mock_model, mock_qwen, mock_torch = _make_vlm_mock(raw_json)

    with patch("vlm_classify._load_model"), \
         patch("vlm_classify._processor", mock_proc), \
         patch("vlm_classify._model", mock_model), \
         patch.dict("sys.modules", {"qwen_vl_utils": mock_qwen, "torch": mock_torch}):
        result = detect_labels(_dummy_image(), ocr_blocks)

    assert "groupings" in result
    assert "invalid_ocr_ids" in result
    assert "missing_words_detected" in result
    assert result["groupings"] == [{"term": "Humerus", "ocr_ids": [0]}]
    assert result["missing_words_detected"] is False


def test_detect_labels_surfaces_invalid_ids_and_missing_flag():
    ocr_blocks = [
        {"id": 0, "text": "Humerus", "x": 10, "y": 10, "w": 50, "h": 20},
        {"id": 1, "text": ".", "x": 200, "y": 100, "w": 5, "h": 5},
    ]
    raw_json = json.dumps({
        "groupings": [{"term": "Humerus", "ocr_ids": [0]}],
        "invalid_ocr_ids": [1],
        "missing_words_detected": True,
    })
    mock_proc, mock_model, mock_qwen, mock_torch = _make_vlm_mock(raw_json)

    with patch("vlm_classify._load_model"), \
         patch("vlm_classify._processor", mock_proc), \
         patch("vlm_classify._model", mock_model), \
         patch.dict("sys.modules", {"qwen_vl_utils": mock_qwen, "torch": mock_torch}):
        result = detect_labels(_dummy_image(), ocr_blocks)

    assert result["invalid_ocr_ids"] == [1]
    assert result["missing_words_detected"] is True


def test_detect_labels_returns_empty_on_empty_ocr_blocks():
    result = detect_labels(_dummy_image(), [])
    assert result == {"groupings": [], "invalid_ocr_ids": [], "missing_words_detected": False}


def test_detect_labels_returns_empty_on_parse_failure():
    ocr_blocks = [{"id": 0, "text": "something", "x": 0, "y": 0, "w": 10, "h": 10}]
    mock_proc, mock_model, mock_qwen, mock_torch = _make_vlm_mock("not valid json at all")

    with patch("vlm_classify._load_model"), \
         patch("vlm_classify._processor", mock_proc), \
         patch("vlm_classify._model", mock_model), \
         patch.dict("sys.modules", {"qwen_vl_utils": mock_qwen, "torch": mock_torch}):
        result = detect_labels(_dummy_image(), ocr_blocks)

    assert result == {"groupings": [], "invalid_ocr_ids": [], "missing_words_detected": False}
```

- [ ] **Step 2: Run tests — expect import errors (the symbols don't exist yet)**

```bash
cd "/home/diem/PT Lernkarten" && python -m pytest pipeline/tests/test_vlm_classify.py -v 2>&1 | head -40
```

Expected: `ImportError` — `_parse_detection_response` not found, `classify` import fails.

---

### Task 2: Refactor `vlm_classify.py`

**Files:**
- Modify: `pipeline/vlm_classify.py`

- [ ] **Step 1: Remove all dead code**

Delete these top-level items (the functions that use them go with them):
- `_UMLAUT_MAP` (dict literal)
- `_VALID_CATEGORIES` (set literal)
- `_USER_PROMPT` (string)
- `_generate_response()` function
- `_parse_response()` function
- `classify()` function
- `_parse_json_tolerant()` function
- `_parse_groupings()` function

Keep: `_SYSTEM_PROMPT`, `_DETECTION_PROMPT`, `_model`, `_processor`, `_load_model()`, `detect_labels()`, `unload_model()`.

- [ ] **Step 2: Replace `_SYSTEM_PROMPT`**

```python
_SYSTEM_PROMPT = (
    "You are an anatomical terminology expert and image quality inspector. "
    "Respond ONLY with a JSON object — no prose, no markdown fences."
)
```

- [ ] **Step 3: Replace `_DETECTION_PROMPT`**

```python
_DETECTION_PROMPT = (
    "I will give you a JSON list of OCR text blocks extracted from an anatomical diagram. "
    "The image you see has RED bounding boxes drawn around each detected OCR region. "
    "Each block has an 'id' and a 'text' field.\n\n"
    "Perform three tasks and return them in a single JSON object:\n"
    "1. GROUPINGS: Reconstruct full anatomical terms by grouping block IDs. "
    "Use every valid block. Fix split words (e.g. 'Promon-' + 'torium' → 'Promontorium') "
    "and obvious OCR typos. Ignore artist signatures and non-anatomical watermarks.\n"
    "2. INVALID IDs: List IDs of blocks that are NOT actual text labels — "
    "dots, pointer-line artifacts, or stray marks mistaken for text by OCR.\n"
    "3. MISSING WORDS: Set missing_words_detected to true if anatomical label text is "
    "visible in the image WITHOUT a RED bounding box around it.\n\n"
    "Return ONLY this JSON object — no prose, no markdown fences:\n"
    '{"groupings": [{"term": "...", "ocr_ids": [1, 2]}], '
    '"invalid_ocr_ids": [3], "missing_words_detected": false}'
)
```

- [ ] **Step 4: Add `_parse_detection_response()` helper**

Place this before `detect_labels`:

```python
def _parse_detection_response(text: str) -> dict:
    """Parse VLM detection JSON → dict with groupings, invalid_ocr_ids, missing_words_detected."""
    _empty: dict = {"groupings": [], "invalid_ocr_ids": [], "missing_words_detected": False}
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        log.warning("VLM detection: no JSON object found in response")
        return _empty
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        log.warning("VLM detection: JSON parse failure")
        return _empty

    groupings = []
    for item in data.get("groupings", []):
        if not isinstance(item, dict) or "term" not in item or "ocr_ids" not in item:
            continue
        try:
            groupings.append({
                "term": str(item["term"]).strip(),
                "ocr_ids": [int(i) for i in item["ocr_ids"]],
            })
        except (TypeError, ValueError):
            continue

    invalid_ocr_ids = []
    for i in data.get("invalid_ocr_ids", []):
        try:
            invalid_ocr_ids.append(int(i))
        except (TypeError, ValueError):
            continue

    missing = bool(data.get("missing_words_detected", False))
    return {"groupings": groupings, "invalid_ocr_ids": invalid_ocr_ids, "missing_words_detected": missing}
```

- [ ] **Step 5: Rewrite `detect_labels()`**

The function now expects `image` to already have red boxes drawn on it (caller's responsibility). It uses `_SYSTEM_PROMPT` at the system level (not a hardcoded string). Return type changes from `list[dict]` to `dict`.

```python
def detect_labels(image: Image.Image, ocr_blocks: list[dict]) -> dict:
    """
    VLM-based OCR grouping with sanity checks.
    image: a copy of the source image with RED bounding boxes already drawn on it.
    Returns {"groupings": [...], "invalid_ocr_ids": [...], "missing_words_detected": bool}.
    On any error, returns the empty/safe version of that dict.
    """
    _empty: dict = {"groupings": [], "invalid_ocr_ids": [], "missing_words_detected": False}
    if not ocr_blocks:
        return _empty
    try:
        _load_model()
        from qwen_vl_utils import process_vision_info
        import torch

        ocr_json = json.dumps(
            [{"id": b["id"], "text": b["text"]} for b in ocr_blocks],
            ensure_ascii=False,
        )
        user_text = _DETECTION_PROMPT + "\n\nOCR blocks:\n" + ocr_json

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": user_text},
                ],
            },
        ]

        text_input = _processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, _ = process_vision_info(messages)
        inputs = _processor(
            text=[text_input], images=image_inputs, padding=True, return_tensors="pt"
        ).to(_model.device)

        with torch.no_grad():
            output_ids = _model.generate(**inputs, max_new_tokens=4096)
        trimmed = output_ids[:, inputs["input_ids"].shape[1]:]
        response = _processor.batch_decode(trimmed, skip_special_tokens=True)[0]

        return _parse_detection_response(response)
    except Exception as exc:
        log.error("Detection failed: %s", exc)
        return _empty
    finally:
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass
```

- [ ] **Step 6: Run tests — all should pass**

```bash
cd "/home/diem/PT Lernkarten" && python -m pytest pipeline/tests/test_vlm_classify.py -v
```

Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
cd "/home/diem/PT Lernkarten" && git add pipeline/vlm_classify.py pipeline/tests/test_vlm_classify.py && git commit -m "refactor(vlm): remove classify(), update detect_labels to return sanity-check dict"
```

---

### Task 3: Refactor `export.py` with tests

**Files:**
- Modify: `pipeline/export.py`
- Modify: `pipeline/tests/test_export.py`

**Note:** `test_export.py` already exists with a `test_build_entry_structure` test that uses the old two-argument signature. That test must be replaced. The `test_save_*` tests cover `save_data_json` which is unchanged — keep them.

- [ ] **Step 1: Replace `test_build_entry_structure`; add new failing tests**

Rewrite the test file. Keep the three `test_save_*` tests verbatim; replace only `test_build_entry_structure` with these:

```python
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from pathlib import Path
from export import build_entry, save_data_json


def test_build_entry_includes_metadata():
    labels = [{
        "text": "Os sacrum",
        "anchor_x": 100,
        "anchor_y": 50.0,
        "mask_box": {"x": 90, "y": 40, "w": 80, "h": 20},
    }]
    entry = build_entry(
        "Knochen-Becken-dorsal-clean.jpg",
        labels,
        category="Knochen",
        subcategory="Becken",
        view="dorsal",
    )
    assert entry["filename"] == "Knochen-Becken-dorsal-clean.jpg"
    assert entry["category"] == "Knochen"
    assert entry["subcategory"] == "Becken"
    assert entry["view"] == "dorsal"


def test_build_entry_labels_passthrough():
    labels = [{
        "text": "Promontorium",
        "anchor_x": 200,
        "anchor_y": 75.5,
        "mask_box": {"x": 190, "y": 65, "w": 100, "h": 25},
    }]
    entry = build_entry(
        "test-clean.jpg",
        labels,
        category="Knochen",
        subcategory="Becken",
        view="ventral",
    )
    label = entry["labels"][0]
    assert label["text"] == "Promontorium"
    assert label["anchor_x"] == 200
    assert label["anchor_y"] == 75.5
    assert label["mask_box"] == {"x": 190, "y": 65, "w": 100, "h": 25}


def test_build_entry_empty_labels():
    entry = build_entry(
        "test-clean.jpg",
        [],
        category="Muskeln",
        subcategory="Arm",
        view="frontal",
    )
    assert entry["labels"] == []


def test_save_creates_parent_dirs(tmp_path):
    entries = [{"filename": "test-clean.jpg", "labels": []}]
    output = tmp_path / "nested" / "dir" / "data.json"
    save_data_json(entries, output)
    assert output.exists()


def test_save_round_trips_json(tmp_path):
    entries = [{"filename": "test-clean.jpg", "labels": [{"x": 1, "y": 2, "w": 3, "h": 4, "text": "Os"}]}]
    output = tmp_path / "data.json"
    save_data_json(entries, output)
    loaded = json.loads(output.read_text(encoding='utf-8'))
    assert loaded == entries


def test_save_preserves_german_chars(tmp_path):
    entries = [{"filename": "f.jpg", "labels": [{"text": "Röntgen-Überblick"}]}]
    output = tmp_path / "data.json"
    save_data_json(entries, output)
    loaded = json.loads(output.read_text(encoding='utf-8'))
    assert loaded[0]["labels"][0]["text"] == "Röntgen-Überblick"
```

- [ ] **Step 2: Run failing tests**

```bash
cd "/home/diem/PT Lernkarten" && python -m pytest pipeline/tests/test_export.py -v
```

Expected: `test_build_entry_includes_metadata` and related tests FAIL — `build_entry() got unexpected keyword arguments 'category'`. The `test_save_*` tests PASS.

- [ ] **Step 3: Rewrite `export.py`**

```python
import json
from pathlib import Path


def build_entry(
    clean_filename: str,
    labels: list,
    *,
    category: str,
    subcategory: str,
    view: str,
) -> dict:
    return {
        "filename": clean_filename,
        "category": category,
        "subcategory": subcategory,
        "view": view,
        "labels": labels,
    }


def save_data_json(entries: list, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: Run tests — should pass**

```bash
cd "/home/diem/PT Lernkarten" && python -m pytest pipeline/tests/test_export.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd "/home/diem/PT Lernkarten" && git add pipeline/export.py pipeline/tests/test_export.py && git commit -m "refactor(export): add category/subcategory/view; label schema gets anchor_x, anchor_y, mask_box"
```

---

### Task 4: Refactor `process.py` (with TDD for new helpers)

**Files:**
- Modify: `pipeline/process.py`
- Create: `pipeline/tests/test_process.py`

The filename-parsing logic is extracted as a small pure helper `_parse_stem` so it can be unit tested before the orchestration code changes.

- [ ] **Step 1: Write failing tests for `_parse_stem`**

```python
# pipeline/tests/test_process.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from process import _parse_stem


def test_parse_stem_simple():
    assert _parse_stem("Knochen-Becken-dorsal") == ("Knochen", "Becken", "dorsal")


def test_parse_stem_complex_subcategory():
    # Subcategory may contain spaces and special characters
    result = _parse_stem("Knochen-Os sacrum & Os Coccygis-dorsal")
    assert result == ("Knochen", "Os sacrum & Os Coccygis", "dorsal")


def test_parse_stem_view_with_spaces():
    assert _parse_stem("Muskeln-Arm-lateral links") == ("Muskeln", "Arm", "lateral links")
```

- [ ] **Step 2: Run failing tests**

```bash
cd "/home/diem/PT Lernkarten" && python -m pytest pipeline/tests/test_process.py -v 2>&1 | head -20
```

Expected: `ImportError` — `_parse_stem` not yet defined in `process.py`.

- [ ] **Step 3: Add `_parse_stem` to `process.py` and verify tests pass**

Add this module-level function near the top of `process.py`, after the constants:

```python
def _parse_stem(stem: str) -> tuple[str, str, str]:
    """Split 'Category-Subcategory-View' filename stem into three metadata parts."""
    parts = stem.split('-', 2)
    return parts[0], parts[1], parts[2]
```

Then run:

```bash
cd "/home/diem/PT Lernkarten" && python -m pytest pipeline/tests/test_process.py -v
```

Expected: All PASS.

- [ ] **Step 4: Update imports**

The current imports stay intact (`detect_labels`, `unload_model`, `remove_text`, `build_entry`, `_union_box`). No changes needed.

- [ ] **Step 5: Replace the Pass 2 loop body**

Find the existing Pass 2 `for path in valid_files:` block (lines ~84–118) and replace its body with:

```python
    for path in valid_files:
        if path not in ocr_results:
            continue
        print(f"[VLM] {path.name} ...")
        image = Image.open(path).convert('RGB')
        img_w, img_h = image.size
        ocr_blocks = ocr_results[path]

        # Parse metadata from filename (format: Category-Subcategory-View.ext)
        category, subcategory, view = _parse_stem(path.stem)

        # Create marked image (red bounding boxes) so VLM can see which regions were detected
        marked_image = remove_text(image, ocr_blocks)
        vlm_result = detect_labels(marked_image, ocr_blocks)

        # Sanity check: warn if VLM sees labels the OCR missed
        if vlm_result["missing_words_detected"]:
            log.warning(
                "VLM reports missing labels in %s — some anatomical terms may lack red boxes; review output manually",
                path.name,
            )

        # Filter out OCR blocks the VLM flagged as artifacts (dots, pointer lines, etc.)
        invalid_ids = set(vlm_result["invalid_ocr_ids"])
        if invalid_ids:
            log.info(
                "Removing %d invalid OCR block(s) flagged by VLM: ids=%s",
                len(invalid_ids),
                sorted(invalid_ids),
            )
        valid_blocks = [b for b in ocr_blocks if b["id"] not in invalid_ids]

        groupings = vlm_result["groupings"]
        if not groupings:
            print(f"  → No groupings from VLM, skipping")
            continue

        # Build labels: anchor = left-centre of the first OCR block; mask_box = union of all blocks
        block_by_id = {b["id"]: b for b in valid_blocks}
        labels = []
        for g in groupings:
            blocks = [block_by_id[i] for i in g["ocr_ids"] if i in block_by_id]
            if not blocks:
                log.warning("No valid OCR blocks for term '%s' (ids=%s)", g["term"], g["ocr_ids"])
                continue
            first = blocks[0]
            anchor_x = first["x"]
            anchor_y = first["y"] + first["h"] / 2
            mask_box = _union_box(blocks, padding=BOX_PADDING, img_w=img_w, img_h=img_h)
            labels.append({
                "text": g["term"],
                "anchor_x": anchor_x,
                "anchor_y": anchor_y,
                "mask_box": mask_box,
            })

        if not labels:
            print(f"  → No valid labels after filtering, skipping")
            continue

        # Inpaint only valid (non-artifact) blocks
        print(f"  → {len(labels)} label(s) grouped, {len(valid_blocks)} valid block(s) to mask")
        clean = remove_text(image, valid_blocks)
        clean_name = f"{path.stem}-clean.jpg"
        clean.save(images_dir / clean_name, 'JPEG', quality=95)
        print(f"  Saved → {clean_name}")
        entries.append(build_entry(
            clean_name,
            labels,
            category=category,
            subcategory=subcategory,
            view=view,
        ))
```

- [ ] **Step 6: Run the full test suite**

```bash
cd "/home/diem/PT Lernkarten" && python -m pytest pipeline/tests/ -v
```

Expected: All tests PASS (including the pre-existing `test_ocr.py` tests).

- [ ] **Step 7: Quick smoke-check — import the module**

```bash
cd "/home/diem/PT Lernkarten/pipeline" && python -c "import process; print('import OK')"
```

Expected: `import OK` (no `ImportError` or `SyntaxError`).

- [ ] **Step 8: Commit**

```bash
cd "/home/diem/PT Lernkarten" && git add pipeline/process.py pipeline/tests/test_process.py && git commit -m "refactor(process): filename metadata via _parse_stem, marked-image VLM input, sanity checks, exact anchor points"
```

---

## Final Verification

- [ ] Run full test suite one more time:

```bash
cd "/home/diem/PT Lernkarten" && python -m pytest pipeline/tests/ -v --tb=short
```

Expected: All PASS, no warnings about removed symbols.

- [ ] Confirm JSON output shape (inspect `web/data/data.json` after a run, or write a quick script):

```json
[
  {
    "filename": "Knochen-Os sacrum & Os Coccygis-dorsal-clean.jpg",
    "category": "Knochen",
    "subcategory": "Os sacrum & Os Coccygis",
    "view": "dorsal",
    "labels": [
      {
        "text": "Promontorium",
        "anchor_x": 340,
        "anchor_y": 182.5,
        "mask_box": {"x": 330, "y": 170, "w": 120, "h": 35}
      }
    ]
  }
]
```

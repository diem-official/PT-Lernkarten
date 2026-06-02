# pipeline/tests/test_process.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
from unittest.mock import patch, MagicMock
from PIL import Image

import process
from process import (
    _parse_stem,
    _write_report,
    _filter_noise_blocks,
    _build_labels_from_terms,
)


def test_parse_stem_simple():
    assert _parse_stem("Anatomie 1-Knochen-Becken-dorsal") == ("Anatomie 1", "Knochen", "Becken", "dorsal")


def test_parse_stem_complex_subcategory():
    # Subcategory may contain spaces and special characters
    result = _parse_stem("Anatomie 1-Knochen-Os sacrum & Os Coccygis-dorsal")
    assert result == ("Anatomie 1", "Knochen", "Os sacrum & Os Coccygis", "dorsal")


def test_parse_stem_view_with_spaces():
    assert _parse_stem("Anatomie 1-Muskeln-Arm-lateral links") == ("Anatomie 1", "Muskeln", "Arm", "lateral links")


def test_write_report(tmp_path):
    _write_report([{"image": "test", "ocr_block_count": 5}], tmp_path / "report.json")
    data = json.loads((tmp_path / "report.json").read_text())
    assert data[0]["image"] == "test"


def test_write_report_overwrites(tmp_path):
    p = tmp_path / "report.json"
    _write_report([{"image": "old"}], p)
    _write_report([{"image": "new"}], p)
    assert json.loads(p.read_text())[0]["image"] == "new"


def _blk(id_, text, x=0, y=0, w=60, h=20):
    return {"id": id_, "text": text, "x": x, "y": y, "w": w, "h": h}




# ── _filter_noise_blocks ──────────────────────────────────────────────────────

def test_filter_noise_removes_single_char():
    blocks = [_blk(0, "A"), _blk(1, "Humerus")]
    assert _filter_noise_blocks(blocks) == [blocks[1]]


def test_filter_noise_removes_non_alpha():
    blocks = [_blk(0, "123"), _blk(1, "..."), _blk(2, "Femur")]
    assert _filter_noise_blocks(blocks) == [blocks[2]]


def test_filter_noise_keeps_valid_blocks():
    blocks = [_blk(0, "Os sacrum"), _blk(1, "Femur")]
    assert _filter_noise_blocks(blocks) == blocks


def test_filter_noise_empty_list():
    assert _filter_noise_blocks([]) == []



# ── _build_labels_from_terms ─────────────────────────────────────────────────

def test_build_labels_creates_label_from_ids():
    ocr = [
        _blk(0, x=10, y=10, w=60, h=20, text="M."),
        _blk(1, x=10, y=35, w=60, h=20, text="biceps"),
    ]
    terms = [{"name": "M. biceps brachii", "ids": [0, 1]}]
    labels, used_ids, orphaned = _build_labels_from_terms(terms, ocr, 800, 600)
    assert len(labels) == 1
    assert labels[0]["text"] == "M. biceps brachii"
    assert labels[0]["anchor_x"] == 10
    assert labels[0]["anchor_y"] == 20.0   # y=10 + h=20 / 2 (topmost block)
    assert "mask_box" in labels[0]
    assert used_ids == {0, 1}
    assert orphaned == []


def test_build_labels_orphans_ids_not_in_pool():
    ocr = [_blk(0, x=10, y=10, w=60, h=20, text="Femur")]
    terms = [{"name": "Ghost", "ids": [99]}]   # id 99 doesn't exist
    labels, used_ids, orphaned = _build_labels_from_terms(terms, ocr, 800, 600)
    assert labels == []
    assert "Ghost" in orphaned
    assert used_ids == set()


def test_build_labels_anchor_is_topmost_block():
    # Block 1 has lower y (higher on page) → must be anchor despite appearing second in ids
    b_low_y  = _blk(1, x=10, y=10, w=60, h=20, text="top")
    b_high_y = _blk(0, x=10, y=50, w=60, h=20, text="bottom")
    terms = [{"name": "Term", "ids": [0, 1]}]
    labels, _, _ = _build_labels_from_terms(terms, [b_low_y, b_high_y], 800, 600)
    # anchor_y must come from the block with y=10 (b_low_y)
    assert labels[0]["anchor_x"] == b_low_y["x"]
    assert labels[0]["anchor_y"] == b_low_y["y"] + b_low_y["h"] / 2

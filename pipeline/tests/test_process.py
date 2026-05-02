# pipeline/tests/test_process.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
from unittest.mock import patch, MagicMock
from PIL import Image

import process
from process import _parse_stem


def test_parse_stem_simple():
    assert _parse_stem("Knochen-Becken-dorsal") == ("Knochen", "Becken", "dorsal")


def test_parse_stem_complex_subcategory():
    # Subcategory may contain spaces and special characters
    result = _parse_stem("Knochen-Os sacrum & Os Coccygis-dorsal")
    assert result == ("Knochen", "Os sacrum & Os Coccygis", "dorsal")


def test_parse_stem_view_with_spaces():
    assert _parse_stem("Muskeln-Arm-lateral links") == ("Muskeln", "Arm", "lateral links")


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


from process import _match_vlm_term

def _blk(id_, text, x=0, y=0, w=60, h=20):
    return {"id": id_, "text": text, "x": x, "y": y, "w": w, "h": h}


def test_partial_match_not_in_labels():
    """_match_vlm_term partial result: box exists, sacri is unmatched."""
    pool = [
        _blk(0, "Ala",   x=10, y=10),
        _blk(1, "ossis", x=10, y=35),
        # "sacri" intentionally absent
    ]
    box, matched, unmatched = _match_vlm_term("Ala ossis sacri", pool, 800, 600)
    assert box is not None
    assert "sacri" in unmatched
    assert len(matched) == 2


def test_partial_match_produces_orphan_not_label(tmp_path):
    """Integration: partial VLM match → orphaned_vlm_terms, NOT in labels/data.json."""
    img = Image.new("RGB", (800, 600))
    ocr_blocks = [
        _blk(0, "Ala",   x=10, y=10),
        _blk(1, "ossis", x=10, y=35),
    ]
    vlm_result = {"terms": ["Ala ossis sacri"]}  # "sacri" not in OCR

    with patch("process.extract_labels", return_value=ocr_blocks), \
         patch("process.unload_engine"), \
         patch("process.detect_labels", return_value=vlm_result), \
         patch("process.unload_model"), \
         patch("process.mask_text", return_value=img), \
         patch("process.draw_boxes", return_value=img), \
         patch("process.build_entry", return_value={}) as mock_build_entry, \
         patch("process.save_data_json"), \
         patch("process.Image.open", return_value=MagicMock(__enter__=lambda s: img, __exit__=lambda *a: None)), \
         patch("process._write_report") as mock_report:

        sys.argv = ["process.py", str(tmp_path)]

        dummy = tmp_path / "Knochen-Becken-dorsal.jpg"
        img.save(str(dummy))

        process.main()

    call_args = mock_report.call_args[0]
    entries = call_args[0]
    assert len(entries) == 1
    qm = entries[0]
    assert "Ala ossis sacri" in qm["orphaned_vlm_terms"]
    assert qm["matched_labels_count"] == 0
    mock_build_entry.assert_not_called()

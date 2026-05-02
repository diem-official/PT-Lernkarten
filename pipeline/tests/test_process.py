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
    _match_vlm_term,
    _filter_noise_blocks,
    _word_tokens,
    _build_word_freq,
    _find_block_containing_word,
    _find_block_near_anchor,
    _build_labels_from_llm_result,
)


def test_parse_stem_simple():
    assert _parse_stem("Knochen-Becken-dorsal") == ("Knochen", "Becken", "dorsal")


def test_parse_stem_complex_subcategory():
    # Subcategory may contain spaces and special characters
    result = _parse_stem("Knochen-Os sacrum & Os Coccygis-dorsal")
    assert result == ("Knochen", "Os sacrum & Os Coccygis", "dorsal")


def test_parse_stem_view_with_spaces():
    assert _parse_stem("Muskeln-Arm-lateral links") == ("Muskeln", "Arm", "lateral links")


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


# ── _word_tokens ──────────────────────────────────────────────────────────────

def test_word_tokens_basic():
    assert _word_tokens("Os sacrum") == ["os", "sacrum"]


def test_word_tokens_strips_punctuation():
    assert _word_tokens("Ala,") == ["ala"]


def test_word_tokens_handles_umlauts():
    tokens = _word_tokens("Größe")
    assert "größe" in tokens


def test_word_tokens_empty_string():
    assert _word_tokens("") == []


# ── _build_word_freq ─────────────────────────────────────────────────────────

def test_build_word_freq_counts_blocks():
    pool = [_blk(0, "Ala ossis"), _blk(1, "Ala sacri")]
    freq = _build_word_freq(pool)
    assert freq["ala"] == 2
    assert freq["ossis"] == 1
    assert freq["sacri"] == 1


def test_build_word_freq_empty_pool():
    assert _build_word_freq([]) == {}


# ── _find_block_containing_word ───────────────────────────────────────────────

def test_find_block_finds_whole_word():
    pool = [_blk(0, "Ala ossis"), _blk(1, "sacri")]
    result = _find_block_containing_word("ossis", pool)
    assert result is pool[0]


def test_find_block_case_insensitive():
    pool = [_blk(0, "Humerus")]
    assert _find_block_containing_word("HUMERUS", pool) is pool[0]


def test_find_block_does_not_match_partial_word():
    # "os" should not match a block containing "ossis"
    pool = [_blk(0, "ossis")]
    assert _find_block_containing_word("os", pool) is None


def test_find_block_returns_none_when_not_found():
    pool = [_blk(0, "Femur")]
    assert _find_block_containing_word("Humerus", pool) is None


# ── _find_block_near_anchor ───────────────────────────────────────────────────

def test_find_near_anchor_finds_close_block():
    # anchor h=20, tolerance = 20*1.5 = 30px
    # |cx diff| = 0, |cy diff| = |45-20| = 25 < 30 → within tolerance ✓
    anchor = _blk(0, "Ala", x=10, y=10, w=60, h=20)
    pool = [
        _blk(1, "ossis", x=10, y=35, w=60, h=20),
        _blk(2, "sacri", x=10, y=200, w=60, h=20),  # too far
    ]
    result = _find_block_near_anchor("ossis", anchor, pool)
    assert result is pool[0]


def test_find_near_anchor_returns_none_when_too_far():
    anchor = _blk(0, "Ala", x=10, y=10, w=60, h=20)
    pool = [_blk(1, "ossis", x=10, y=200, w=60, h=20)]
    result = _find_block_near_anchor("ossis", anchor, pool)
    assert result is None


def test_find_near_anchor_returns_closest_when_multiple():
    anchor = _blk(0, "Ala", x=10, y=10, w=60, h=20)
    close = _blk(1, "ossis", x=10, y=32, w=60, h=20)
    far   = _blk(2, "ossis", x=10, y=38, w=60, h=20)
    pool  = [far, close]   # reversed — closest must win
    result = _find_block_near_anchor("ossis", anchor, pool)
    assert result is close


# ── _match_vlm_term ───────────────────────────────────────────────────────────

def test_match_phase1_exact_match():
    pool = [_blk(0, "Promontorium", x=10, y=10)]
    box, matched, unmatched = _match_vlm_term("Promontorium", pool, 800, 600)
    assert box is not None
    assert len(matched) == 1
    assert unmatched == []
    assert pool == []   # block removed from pool


def test_match_phase1_case_insensitive():
    pool = [_blk(0, "promontorium")]
    box, matched, unmatched = _match_vlm_term("Promontorium", pool, 800, 600)
    assert box is not None
    assert unmatched == []
    assert pool == []   # matched block removed


def test_match_phase2_3_multi_word_all_found():
    # anchor "Ala" at y=10 h=20 → center_y=20, tolerance=30
    # "ossis" center_y=25 (y=15), distance=5 < 30 ✓
    # "sacri" center_y=35 (y=25), distance=15 < 30 ✓
    pool = [
        _blk(0, "Ala",   x=10, y=10, h=20),
        _blk(1, "ossis", x=10, y=15, h=20),
        _blk(2, "sacri", x=10, y=25, h=20),
    ]
    box, matched, unmatched = _match_vlm_term("Ala ossis sacri", pool, 800, 600)
    assert box is not None
    assert unmatched == []
    assert len(matched) == 3
    assert pool == []   # all blocks consumed


def test_match_partial_first_word_missing():
    """When the first word is absent from the pool, the remaining words become anchor+proximity."""
    pool = [
        # "Ala" intentionally absent
        _blk(1, "ossis", x=10, y=10, h=20),
        _blk(2, "sacri", x=10, y=25, h=20),
    ]
    box, matched, unmatched = _match_vlm_term("Ala ossis sacri", pool, 800, 600)
    assert box is not None
    assert "Ala" in unmatched
    assert len(matched) == 2


def test_match_no_blocks_found():
    pool = [_blk(0, "Femur")]
    box, matched, unmatched = _match_vlm_term("Os sacrum", pool, 800, 600)
    assert box is None
    assert matched == []
    assert set(unmatched) == {"Os", "sacrum"}


def test_match_single_word_no_match_returns_none():
    pool = [_blk(0, "Femur")]
    box, matched, unmatched = _match_vlm_term("Humerus", pool, 800, 600)
    assert box is None
    assert matched == []
    assert "Humerus" in unmatched


def test_match_selects_rarest_word_as_anchor():
    """Phase 2 should select the rarest word in the pool as anchor, not the first word."""
    # "Ala" appears in 2 blocks; "sacri" appears in 1 → "sacri" must be anchor
    pool = [
        _blk(0, "Ala",   x=10, y=10, h=20),
        _blk(1, "Ala",   x=10, y=50, h=20),  # duplicate "Ala" → freq 2
        _blk(2, "sacri", x=10, y=25, h=20),  # freq 1 → should be anchor
    ]
    box, matched, unmatched = _match_vlm_term("Ala sacri", pool, 800, 600)
    assert box is not None
    assert unmatched == []
    # Both "Ala" blocks should NOT both be matched — only the one near "sacri"
    # "sacri" is at y=25 (center=35), anchor-based search finds "Ala" at y=10 (center=20)
    # distance = 15 < 30 ✓ — the closer "Ala" block (id=0) should match
    assert len(matched) == 2
    assert pool == [_blk(1, "Ala", x=10, y=50, h=20)]   # unreachable "Ala" remains


def test_match_does_not_mutate_other_pool_blocks():
    """Blocks not matched for this term must remain in the pool."""
    pool = [
        _blk(0, "Promontorium", x=10, y=10),
        _blk(1, "Femur",        x=200, y=200),
    ]
    _match_vlm_term("Promontorium", pool, 800, 600)
    assert len(pool) == 1
    assert pool[0]["text"] == "Femur"


# ── _build_labels_from_llm_result ─────────────────────────────────────────────

def test_build_labels_creates_label_from_ids():
    ocr = [
        _blk(0, x=10, y=10, w=60, h=20, text="M."),
        _blk(1, x=10, y=35, w=60, h=20, text="biceps"),
    ]
    terms = [{"name": "M. biceps brachii", "ids": [0, 1]}]
    labels, used_ids, orphaned = _build_labels_from_llm_result(terms, ocr, 800, 600)
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
    labels, used_ids, orphaned = _build_labels_from_llm_result(terms, ocr, 800, 600)
    assert labels == []
    assert "Ghost" in orphaned
    assert used_ids == set()


def test_build_labels_anchor_is_topmost_block():
    # Block 1 has lower y (higher on page) → must be anchor despite appearing second in ids
    b_low_y  = _blk(1, x=10, y=10, w=60, h=20, text="top")
    b_high_y = _blk(0, x=10, y=50, w=60, h=20, text="bottom")
    terms = [{"name": "Term", "ids": [0, 1]}]
    labels, _, _ = _build_labels_from_llm_result(terms, [b_low_y, b_high_y], 800, 600)
    # anchor_y must come from the block with y=10 (b_low_y)
    assert labels[0]["anchor_x"] == b_low_y["x"]
    assert labels[0]["anchor_y"] == b_low_y["y"] + b_low_y["h"] / 2

# pipeline/tests/test_llm_classify.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
from unittest.mock import patch, MagicMock

import llm_classify
from llm_classify import _group_bundles, _vote_terms, detect_labels, _parse_bundle_response


def _blk(id_, x, y, w, h, text="X"):
    return {"id": id_, "text": text, "x": x, "y": y, "w": w, "h": h}


# ── _group_bundles ────────────────────────────────────────────────────────────

def test_group_bundles_anchor_included_in_own_bundle():
    blk = _blk(0, x=10, y=10, w=60, h=20)
    result = _group_bundles([blk])
    assert len(result) == 1
    assert blk in result[0]


def test_group_bundles_vertical_corridor_includes_block_below():
    # anchor h=20 → corridor y in [10, 10 + 10*20] = [10, 210]
    anchor = _blk(0, x=10, y=10, w=60, h=20)
    below  = _blk(1, x=10, y=100, w=60, h=20)   # y=100 ≤ 210, x-overlap ✓
    result = _group_bundles([anchor, below])
    bundle_for_anchor = next(b for b in result if anchor in b)
    assert below in bundle_for_anchor


def test_group_bundles_excludes_block_too_far_below():
    # anchor h=20 → ceiling y = 10 + 10*20 = 210; block at y=220 is out
    anchor = _blk(0, x=10, y=10, w=60, h=20)
    far    = _blk(1, x=10, y=220, w=60, h=20)
    result = _group_bundles([anchor, far])
    bundle_for_anchor = next(b for b in result if anchor in b)
    assert far not in bundle_for_anchor


def test_group_bundles_excludes_block_above_anchor():
    anchor = _blk(0, x=10, y=100, w=60, h=20)
    above  = _blk(1, x=10, y=50,  w=60, h=20)   # y=50 < anchor.y=100
    result = _group_bundles([anchor, above])
    bundle_for_anchor = next(b for b in result if anchor in b)
    assert above not in bundle_for_anchor


def test_group_bundles_x_overlap_required():
    # anchor x=10..70; candidate x=200..260 → no overlap
    anchor     = _blk(0, x=10,  y=10, w=60, h=20)
    no_overlap = _blk(1, x=200, y=20, w=60, h=20)
    result = _group_bundles([anchor, no_overlap])
    bundle_for_anchor = next(b for b in result if anchor in b)
    assert no_overlap not in bundle_for_anchor


def test_group_bundles_bundle_sorted_by_y():
    anchor = _blk(0, x=10, y=10, w=60, h=20)
    b1     = _blk(1, x=10, y=50, w=60, h=20)
    b2     = _blk(2, x=10, y=30, w=60, h=20)
    result = _group_bundles([anchor, b1, b2])
    bundle_for_anchor = next(b for b in result if anchor in b)
    ys = [b["y"] for b in bundle_for_anchor]
    assert ys == sorted(ys)


def test_group_bundles_each_anchor_produces_one_bundle():
    a = _blk(0, x=10,  y=10,  w=60, h=20)
    b = _blk(1, x=200, y=200, w=60, h=20)   # no x-overlap → each is its own bundle
    result = _group_bundles([a, b])
    assert len(result) == 2


def test_group_bundles_empty_input():
    assert _group_bundles([]) == []


# ── _vote_terms ───────────────────────────────────────────────────────────────

def test_vote_terms_accepts_sig_with_enough_votes():
    responses = [
        [{"name": "M. biceps brachii", "ids": [1, 2]}],
        [{"name": "M. biceps brachii", "ids": [1, 2]}],
        [{"name": "M. biceps brachii", "ids": [1, 2]}],
    ]
    result = _vote_terms(responses, min_votes=3)
    assert len(result) == 1
    assert result[0]["name"] == "M. biceps brachii"
    assert sorted(result[0]["ids"]) == [1, 2]


def test_vote_terms_rejects_sig_below_threshold():
    responses = [
        [{"name": "M. biceps brachii", "ids": [1, 2]}],
        [{"name": "M. biceps brachii", "ids": [1, 2]}],
    ]
    result = _vote_terms(responses, min_votes=3)
    assert result == []


def test_vote_terms_sig_is_order_independent():
    responses = [
        [{"name": "M. biceps brachii", "ids": [2, 1]}],
        [{"name": "M. biceps brachii", "ids": [1, 2]}],
        [{"name": "M. biceps brachii", "ids": [1, 2]}],
    ]
    result = _vote_terms(responses, min_votes=3)
    assert len(result) == 1


def test_vote_terms_picks_most_voted_name():
    responses = [
        [{"name": "Promontorium",  "ids": [5]}],
        [{"name": "Promontorium",  "ids": [5]}],
        [{"name": "Promontoriom",  "ids": [5]}],   # OCR artefact — minority
    ]
    result = _vote_terms(responses, min_votes=3)
    assert len(result) == 1
    assert result[0]["name"] == "Promontorium"


def test_vote_terms_two_independent_sigs_both_accepted():
    responses = [
        [{"name": "Femur", "ids": [0]}, {"name": "Humerus", "ids": [1]}],
        [{"name": "Femur", "ids": [0]}, {"name": "Humerus", "ids": [1]}],
        [{"name": "Femur", "ids": [0]}, {"name": "Humerus", "ids": [1]}],
    ]
    result = _vote_terms(responses, min_votes=3)
    names = {t["name"] for t in result}
    assert names == {"Femur", "Humerus"}


def test_vote_terms_empty_responses():
    assert _vote_terms([], min_votes=3) == []


def test_vote_terms_all_empty_bundles():
    assert _vote_terms([[], [], []], min_votes=3) == []


# ── _parse_bundle_response ────────────────────────────────────────────────────

def test_parse_bundle_valid():
    raw = json.dumps({"terms": [{"name": "M. biceps brachii", "ids": [1, 2, 3]}]})
    result = _parse_bundle_response(raw)
    assert result == [{"name": "M. biceps brachii", "ids": [1, 2, 3]}]


def test_parse_bundle_strips_whitespace_from_name():
    raw = json.dumps({"terms": [{"name": "  Femur  ", "ids": [0]}]})
    assert _parse_bundle_response(raw)[0]["name"] == "Femur"


def test_parse_bundle_skips_missing_name():
    raw = json.dumps({"terms": [{"ids": [0]}]})
    assert _parse_bundle_response(raw) == []


def test_parse_bundle_skips_missing_ids():
    raw = json.dumps({"terms": [{"name": "Femur"}]})
    assert _parse_bundle_response(raw) == []


def test_parse_bundle_skips_non_int_ids():
    raw = json.dumps({"terms": [{"name": "Femur", "ids": ["a", "b"]}]})
    assert _parse_bundle_response(raw) == []


def test_parse_bundle_invalid_json_returns_empty():
    assert _parse_bundle_response("not json") == []


def test_parse_bundle_strips_prose_wrapper():
    inner = json.dumps({"terms": [{"name": "Humerus", "ids": [7]}]})
    raw = f"Sure! Here is the answer: {inner} Hope that helps."
    result = _parse_bundle_response(raw)
    assert result == [{"name": "Humerus", "ids": [7]}]


# ── detect_labels() — LLM mocked ─────────────────────────────────────────────

def _make_llm_mock(raw_json: str):
    mock_tok = MagicMock()
    mock_tok.apply_chat_template.return_value = "tmpl"
    mock_inputs = MagicMock()
    mock_inputs.to.return_value = mock_inputs
    mock_inputs.__getitem__ = MagicMock(return_value=MagicMock(shape=[1, 10]))
    mock_tok.return_value = mock_inputs
    mock_tok.batch_decode.return_value = [raw_json]

    mock_model = MagicMock()
    mock_model.device = "cpu"

    mock_torch = MagicMock()
    mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
    mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=False)

    return mock_tok, mock_model, mock_torch


def test_detect_labels_empty_ocr_returns_empty():
    assert detect_labels([]) == {"terms": []}


def test_detect_labels_returns_error_on_model_exception():
    ocr_blocks = [_blk(0, 10, 10, 50, 20, text="Humerus")]
    mock_tok, mock_model, mock_torch = _make_llm_mock("{}")
    mock_model.generate.side_effect = RuntimeError("CUDA out of memory")

    with patch("llm_classify._load_model"), \
         patch("llm_classify._tokenizer", mock_tok), \
         patch("llm_classify._model", mock_model), \
         patch.dict("sys.modules", {"torch": mock_torch}):
        result = detect_labels(ocr_blocks)

    assert result.get("error") is True
    assert result["terms"] == []


def test_detect_labels_consensus_filters_low_vote_terms():
    """Single block → 1 bundle → 1 vote → below min_votes=3 → empty result."""
    ocr_blocks = [_blk(0, 10, 10, 50, 20, text="Humerus")]
    raw = json.dumps({"terms": [{"name": "Humerus", "ids": [0]}]})
    mock_tok, mock_model, mock_torch = _make_llm_mock(raw)

    with patch("llm_classify._load_model"), \
         patch("llm_classify._tokenizer", mock_tok), \
         patch("llm_classify._model", mock_model), \
         patch.dict("sys.modules", {"torch": mock_torch}):
        result = detect_labels(ocr_blocks)

    assert result["terms"] == []


def test_detect_labels_returns_structured_terms_when_votes_sufficient():
    """Three vertically overlapping blocks → 3 bundles each seeing ids [0,1] → 3 votes → accepted."""
    # Block 0 (y=10, h=20): corridor [10..210]
    # Block 1 (y=30, h=20): corridor [30..230], sees block 0 (y=10 < 30, excluded!) — wait
    # Actually y=10 < y_start=30, so block 0 is above block 1's anchor → NOT included.
    # To get 3 votes for ids=[0,1], we need 3 anchors whose corridors include BOTH block 0 AND block 1.
    # Use 3 anchor blocks above block 0 that have x-overlap and corridors spanning both 0 and 1.
    # Anchors at y=0 with h=5 → corridor [0..50], includes block 0 (y=10) and block 1 (y=30).
    a0 = _blk(10, x=10, y=0,  w=60, h=5)   # anchor, corridor [0..50]
    a1 = _blk(11, x=10, y=1,  w=60, h=5)   # anchor, corridor [1..51]
    a2 = _blk(12, x=10, y=2,  w=60, h=5)   # anchor, corridor [2..52]
    b0 = _blk(0,  x=10, y=10, w=60, h=20)  # term block 1
    b1 = _blk(1,  x=10, y=30, w=60, h=20)  # term block 2

    ocr_blocks = [a0, a1, a2, b0, b1]
    # LLM always returns ids [0, 1] regardless of bundle
    raw = json.dumps({"terms": [{"name": "M. biceps brachii", "ids": [0, 1]}]})
    mock_tok, mock_model, mock_torch = _make_llm_mock(raw)

    with patch("llm_classify._load_model"), \
         patch("llm_classify._tokenizer", mock_tok), \
         patch("llm_classify._model", mock_model), \
         patch.dict("sys.modules", {"torch": mock_torch}):
        result = detect_labels(ocr_blocks)

    assert len(result["terms"]) == 1
    assert result["terms"][0]["name"] == "M. biceps brachii"
    assert sorted(result["terms"][0]["ids"]) == [0, 1]

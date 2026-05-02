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

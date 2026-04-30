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

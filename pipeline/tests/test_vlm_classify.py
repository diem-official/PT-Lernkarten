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


def test_detect_labels_returns_empty_on_model_exception():
    ocr_blocks = [{"id": 0, "text": "Humerus", "x": 10, "y": 10, "w": 50, "h": 20}]
    mock_proc, mock_model, mock_qwen, mock_torch = _make_vlm_mock("{}")
    mock_model.generate.side_effect = RuntimeError("CUDA out of memory")

    with patch("vlm_classify._load_model"), \
         patch("vlm_classify._processor", mock_proc), \
         patch("vlm_classify._model", mock_model), \
         patch.dict("sys.modules", {"qwen_vl_utils": mock_qwen, "torch": mock_torch}):
        result = detect_labels(_dummy_image(), ocr_blocks)

    assert result == {"groupings": [], "invalid_ocr_ids": [], "missing_words_detected": False}

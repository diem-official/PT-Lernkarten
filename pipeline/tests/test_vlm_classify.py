# pipeline/tests/test_vlm_classify.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image

from vlm_classify import _parse_terms_response, detect_labels


# ── _parse_terms_response() — pure, no model ─────────────────────────────────

def test_parse_terms_valid_list():
    raw = json.dumps({"terms": ["Ala ossis sacri", "Promontorium"]})
    result = _parse_terms_response(raw)
    assert result == ["Ala ossis sacri", "Promontorium"]


def test_parse_terms_strips_whitespace():
    raw = json.dumps({"terms": ["  Os sacrum  ", " Caput femoris"]})
    result = _parse_terms_response(raw)
    assert result == ["Os sacrum", "Caput femoris"]


def test_parse_terms_skips_empty_strings():
    raw = json.dumps({"terms": ["Valid term", "", "   ", "Another"]})
    result = _parse_terms_response(raw)
    assert result == ["Valid term", "Another"]


def test_parse_terms_skips_non_strings():
    raw = json.dumps({"terms": ["Valid", 42, None, "Also valid"]})
    result = _parse_terms_response(raw)
    assert result == ["Valid", "Also valid"]


def test_parse_terms_invalid_json_returns_empty():
    assert _parse_terms_response("not json") == []


def test_parse_terms_no_braces_returns_empty():
    assert _parse_terms_response("[1, 2, 3]") == []


def test_parse_terms_missing_key_returns_empty():
    raw = json.dumps({"other_key": ["something"]})
    result = _parse_terms_response(raw)
    assert result == []


def test_parse_terms_strips_prose_wrapper():
    """VLM sometimes wraps JSON in prose — regex must extract the object."""
    raw = 'Here is the result: ' + json.dumps({"terms": ["Basis ossis sacri"]}) + ' Done.'
    result = _parse_terms_response(raw)
    assert result == ["Basis ossis sacri"]


# ── detect_labels() — model mocked ───────────────────────────────────────────

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


def test_detect_labels_returns_terms_list():
    ocr_blocks = [{"id": 0, "text": "Humerus", "x": 10, "y": 10, "w": 50, "h": 20}]
    raw_json = json.dumps({"terms": ["Humerus", "Caput humeri"]})
    mock_proc, mock_model, mock_qwen, mock_torch = _make_vlm_mock(raw_json)

    with patch("vlm_classify._load_model"), \
         patch("vlm_classify._processor", mock_proc), \
         patch("vlm_classify._model", mock_model), \
         patch.dict("sys.modules", {"qwen_vl_utils": mock_qwen, "torch": mock_torch}):
        result = detect_labels(_dummy_image(), ocr_blocks)

    assert result == {"terms": ["Humerus", "Caput humeri"]}


def test_detect_labels_returns_empty_on_empty_ocr_blocks():
    result = detect_labels(_dummy_image(), [])
    assert result == {"terms": []}


def test_detect_labels_returns_error_on_model_exception():
    ocr_blocks = [{"id": 0, "text": "Humerus", "x": 10, "y": 10, "w": 50, "h": 20}]
    mock_proc, mock_model, mock_qwen, mock_torch = _make_vlm_mock("{}")
    mock_model.generate.side_effect = RuntimeError("CUDA out of memory")

    with patch("vlm_classify._load_model"), \
         patch("vlm_classify._processor", mock_proc), \
         patch("vlm_classify._model", mock_model), \
         patch.dict("sys.modules", {"qwen_vl_utils": mock_qwen, "torch": mock_torch}):
        result = detect_labels(_dummy_image(), ocr_blocks)

    assert result.get("error") is True
    assert result["terms"] == []


def test_detect_labels_parse_failure_returns_empty_terms():
    ocr_blocks = [{"id": 0, "text": "something", "x": 0, "y": 0, "w": 10, "h": 10}]
    mock_proc, mock_model, mock_qwen, mock_torch = _make_vlm_mock("not valid json at all")

    with patch("vlm_classify._load_model"), \
         patch("vlm_classify._processor", mock_proc), \
         patch("vlm_classify._model", mock_model), \
         patch.dict("sys.modules", {"qwen_vl_utils": mock_qwen, "torch": mock_torch}):
        result = detect_labels(_dummy_image(), ocr_blocks)

    assert result["terms"] == []
    assert "error" not in result   # parse failure is not a hard error

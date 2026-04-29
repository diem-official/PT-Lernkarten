from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ocr import extract_labels


def _mock_ocr(results):
    mock = MagicMock()
    mock.ocr.return_value = results
    return mock


def test_bbox_converted_to_xywh():
    # PaddleOCR bbox: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
    bbox = [[10, 20], [110, 20], [110, 50], [10, 50]]
    mock_result = [[[bbox, ("Humerus", 0.95)]]]
    with patch('ocr.PaddleOCR', return_value=_mock_ocr(mock_result)):
        labels = extract_labels("fake.jpg")
    assert labels == [{"x": 10, "y": 20, "w": 100, "h": 30, "text": "Humerus"}]


def test_low_confidence_filtered_out():
    bbox = [[10, 20], [110, 20], [110, 50], [10, 50]]
    mock_result = [[[bbox, ("noise", 0.3)]]]
    with patch('ocr.PaddleOCR', return_value=_mock_ocr(mock_result)):
        labels = extract_labels("fake.jpg")
    assert labels == []


def test_empty_image_returns_empty():
    with patch('ocr.PaddleOCR', return_value=_mock_ocr([[None]])):
        labels = extract_labels("fake.jpg")
    assert labels == []


def test_blank_text_filtered_out():
    bbox = [[10, 20], [110, 20], [110, 50], [10, 50]]
    mock_result = [[[bbox, ("  ", 0.99)]]]
    with patch('ocr.PaddleOCR', return_value=_mock_ocr(mock_result)):
        labels = extract_labels("fake.jpg")
    assert labels == []

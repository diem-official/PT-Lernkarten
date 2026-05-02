from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ocr import extract_labels, _union_box


# ── extract_labels() ─────────────────────────────────────────────────────────

def _mock_engine(texts=(), scores=(), boxes=()):
    mock = MagicMock()
    mock.predict.return_value = [{'rec_texts': list(texts), 'rec_scores': list(scores), 'rec_boxes': list(boxes)}]
    return mock


def test_extract_labels_converts_box_to_xywh():
    engine = _mock_engine(texts=['Humerus'], scores=[0.95], boxes=[[10, 20, 110, 50]])
    with patch('ocr._get_engine', return_value=engine):
        labels = extract_labels('fake.jpg')
    assert labels == [{'id': 0, 'x': 10, 'y': 20, 'w': 100, 'h': 30, 'text': 'Humerus'}]


def test_extract_labels_ids_are_sequential():
    engine = _mock_engine(
        texts=['Humerus', 'Femur'],
        scores=[0.95, 0.9],
        boxes=[[10, 20, 110, 50], [200, 100, 300, 130]],
    )
    with patch('ocr._get_engine', return_value=engine):
        labels = extract_labels('fake.jpg')
    assert labels[0]['id'] == 0
    assert labels[1]['id'] == 1


def test_extract_labels_filters_low_confidence():
    engine = _mock_engine(texts=['noise'], scores=[0.3], boxes=[[10, 20, 110, 50]])
    with patch('ocr._get_engine', return_value=engine):
        labels = extract_labels('fake.jpg')
    assert labels == []


def test_extract_labels_empty_result():
    mock = MagicMock()
    mock.predict.return_value = []
    with patch('ocr._get_engine', return_value=mock):
        labels = extract_labels('fake.jpg')
    assert labels == []


# ── _union_box() ─────────────────────────────────────────────────────────────

def test_union_box_single_block():
    blocks = [{'x': 10, 'y': 20, 'w': 100, 'h': 30}]
    result = _union_box(blocks, padding=5, img_w=800, img_h=600)
    assert result == {'x': 5, 'y': 15, 'w': 110, 'h': 40}


def test_union_box_multiple_blocks():
    blocks = [
        {'x': 10, 'y': 20, 'w': 40, 'h': 20},
        {'x': 60, 'y': 15, 'w': 50, 'h': 25},
    ]
    result = _union_box(blocks, padding=0, img_w=800, img_h=600)
    assert result == {'x': 10, 'y': 15, 'w': 100, 'h': 25}


def test_union_box_clamps_to_image():
    blocks = [{'x': 0, 'y': 0, 'w': 790, 'h': 590}]
    result = _union_box(blocks, padding=20, img_w=800, img_h=600)
    assert result['x'] == 0
    assert result['y'] == 0
    assert result['w'] == 800
    assert result['h'] == 600

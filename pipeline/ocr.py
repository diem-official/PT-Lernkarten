try:
    from paddleocr import PaddleOCR
except ImportError:  # pragma: no cover – satisfied at runtime on GPU machine
    PaddleOCR = None  # type: ignore

_ocr_engine = None


def _get_engine():
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = PaddleOCR(use_textline_orientation=True, lang='german')
    return _ocr_engine


def extract_labels(image_path: str) -> list:
    """Run OCR on image_path. Returns list of {x, y, w, h, text} dicts."""
    engine = _get_engine()
    result = engine.predict(image_path)

    labels = []
    if not result:
        return labels

    res = result[0]
    texts = res.get('rec_texts', [])
    scores = res.get('rec_scores', [])
    boxes = res.get('rec_boxes', [])  # shape (N, 4): x_min, y_min, x_max, y_max

    for text, score, box in zip(texts, scores, boxes):
        if score < 0.5 or not text.strip():
            continue
        x_min, y_min, x_max, y_max = int(box[0]), int(box[1]), int(box[2]), int(box[3])
        labels.append({
            "x": x_min,
            "y": y_min,
            "w": x_max - x_min,
            "h": y_max - y_min,
            "text": text.strip(),
        })
    return labels

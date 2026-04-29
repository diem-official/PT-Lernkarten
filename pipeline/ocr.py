try:
    from paddleocr import PaddleOCR
except ImportError:  # pragma: no cover – satisfied at runtime on GPU machine
    PaddleOCR = None  # type: ignore

_ocr_engine = None


def _get_engine():
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = PaddleOCR(use_angle_cls=True, lang='german', show_log=False)
    return _ocr_engine


def extract_labels(image_path: str) -> list:
    """Run OCR on image_path. Returns list of {x, y, w, h, text} dicts."""
    engine = _get_engine()
    result = engine.ocr(image_path, cls=True)

    labels = []
    if not result or not result[0]:
        return labels

    for line in result[0]:
        if line is None:
            continue
        bbox, (text, confidence) = line
        if confidence < 0.5 or not text.strip():
            continue
        # min/max over all 4 corners gives the axis-aligned bounding box.
        # For rotated text, this box is slightly larger than the actual glyph region,
        # which is acceptable for this use case (mostly upright printed anatomy labels).
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        labels.append({
            "x": int(min(xs)),
            "y": int(min(ys)),
            "w": int(max(xs) - min(xs)),
            "h": int(max(ys) - min(ys)),
            "text": text.strip(),
        })
    return labels

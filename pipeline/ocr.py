import gc
import logging

try:
    from paddleocr import PaddleOCR
except ImportError:  # pragma: no cover – satisfied at runtime on GPU machine
    PaddleOCR = None  # type: ignore

log = logging.getLogger("ocr")

_ocr_engine = None


def _get_engine():
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = PaddleOCR(
            use_textline_orientation=False, 
            use_doc_unwarping=False, 
            lang='german',
            det_limit_side_len=4000, 
            det_db_box_thresh=0.5)
    return _ocr_engine


def unload_engine() -> None:
    """Release the PaddleOCR engine and free GPU memory before loading the LLM."""
    global _ocr_engine
    _ocr_engine = None
    gc.collect()
    try:
        import paddle
        paddle.device.cuda.empty_cache()
    except Exception:
        pass
    log.info("PaddleOCR engine unloaded from GPU.")


def extract_labels(image_path: str) -> list:
    """Run OCR on image_path. Returns list of {id, x, y, w, h, text} dicts."""
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
        if score < 0.3 or not text.strip():
            continue

        if len(box) > 0 and hasattr(box[0], "__iter__"):
            # Handle polygon format: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
            x_min = int(min(p[0] for p in box))
            y_min = int(min(p[1] for p in box))
            x_max = int(max(p[0] for p in box))
            y_max = int(max(p[1] for p in box))
        else:
            # Fallback for flat format: [x_min, y_min, x_max, y_max]
            x_min, y_min, x_max, y_max = int(box[0]), int(box[1]), int(box[2]), int(box[3])

        labels.append({
            "id": len(labels),
            "x": x_min,
            "y": y_min,
            "w": x_max - x_min,
            "h": y_max - y_min,
            "text": text.strip(),
        })

    # Manually clear GPU cache to prevent memory fragmentation
    gc.collect()
    try:
        import paddle
        paddle.device.cuda.empty_cache()
    except Exception:
        pass
    return labels


def _union_box(blocks: list, padding: int, img_w: int, img_h: int) -> dict:
    """Union bounding box of all blocks with padding, clamped to image dimensions."""
    x0 = max(0, min(b["x"] for b in blocks) - padding)
    y0 = max(0, min(b["y"] for b in blocks) - padding)
    x1 = min(img_w, max(b["x"] + b["w"] for b in blocks) + padding)
    y1 = min(img_h, max(b["y"] + b["h"] for b in blocks) + padding)
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}

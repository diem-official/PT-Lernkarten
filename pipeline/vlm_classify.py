import json
import logging
import re

from PIL import Image

log = logging.getLogger("vlm_classify")

_SYSTEM_PROMPT = (
    "You are an anatomical terminology expert and image quality inspector. "
    "Respond ONLY with a JSON object — no prose, no markdown fences."
)

_DETECTION_PROMPT = (
    "I will give you a JSON list of OCR text blocks extracted from an anatomical diagram. "
    "The image you see has RED bounding boxes drawn around each detected OCR region. "
    "Each block has an 'id' and a 'text' field.\n\n"
    "Perform three tasks and return them in a single JSON object:\n"
    "1. GROUPINGS: Reconstruct full anatomical terms by grouping block IDs. "
    "Use every valid block. Fix split words (e.g. 'Promon-' + 'torium' → 'Promontorium') "
    "and obvious OCR typos. Ignore artist signatures and non-anatomical watermarks.\n"
    "2. INVALID IDs: List IDs of blocks that are NOT actual text labels — "
    "dots, pointer-line artifacts, or stray marks mistaken for text by OCR.\n"
    "3. MISSING WORDS: Set missing_words_detected to true if anatomical label text is "
    "visible in the image WITHOUT a RED bounding box around it.\n\n"
    "Return ONLY this JSON object — no prose, no markdown fences:\n"
    '{"groupings": [{"term": "...", "ocr_ids": [1, 2]}], '
    '"invalid_ocr_ids": [3], "missing_words_detected": false}'
)

_model = None
_processor = None


def _load_model() -> None:
    global _model, _processor
    if _model is not None:
        return
    import torch
    from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor

    log.info("Loading Qwen2.5-VL-7B-Instruct …")
    model_id = "Qwen/Qwen2.5-VL-7B-Instruct"
    # Load into locals first so globals are only set when both succeed
    proc = AutoProcessor.from_pretrained(model_id)
    mdl = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        device_map="auto",  # "auto" works on GPU and CPU; 3090 Ti will use cuda:0
    )
    mdl.eval()
    _processor, _model = proc, mdl
    log.info("Model loaded.")


def _parse_detection_response(text: str) -> dict:
    """Parse VLM detection JSON → dict with groupings, invalid_ocr_ids, missing_words_detected."""
    _empty: dict = {"groupings": [], "invalid_ocr_ids": [], "missing_words_detected": False}
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        log.warning("VLM detection: no JSON object found in response")
        return _empty
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        log.warning("VLM detection: JSON parse failure")
        return _empty

    groupings = []
    for item in data.get("groupings", []):
        if not isinstance(item, dict) or "term" not in item or "ocr_ids" not in item:
            continue
        try:
            groupings.append({
                "term": str(item["term"]).strip(),
                "ocr_ids": [int(i) for i in item["ocr_ids"]],
            })
        except (TypeError, ValueError):
            continue

    invalid_ocr_ids = []
    for i in data.get("invalid_ocr_ids", []):
        try:
            invalid_ocr_ids.append(int(i))
        except (TypeError, ValueError):
            continue

    missing = bool(data.get("missing_words_detected", False))
    return {"groupings": groupings, "invalid_ocr_ids": invalid_ocr_ids, "missing_words_detected": missing}


def detect_labels(image: Image.Image, ocr_blocks: list[dict]) -> dict:
    """
    VLM-based OCR grouping with sanity checks.
    image: a copy of the source image with RED bounding boxes already drawn on it.
    Returns {"groupings": [...], "invalid_ocr_ids": [...], "missing_words_detected": bool}.
    On any error, returns the empty/safe version of that dict.
    """
    _empty: dict = {"groupings": [], "invalid_ocr_ids": [], "missing_words_detected": False}
    if not ocr_blocks:
        return _empty
    try:
        _load_model()
        from qwen_vl_utils import process_vision_info
        import torch

        ocr_json = json.dumps(
            [{"id": b["id"], "text": b["text"]} for b in ocr_blocks],
            ensure_ascii=False,
        )
        user_text = _DETECTION_PROMPT + "\n\nOCR blocks:\n" + ocr_json

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": user_text},
                ],
            },
        ]

        text_input = _processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, _ = process_vision_info(messages)
        inputs = _processor(
            text=[text_input], images=image_inputs, padding=True, return_tensors="pt"
        ).to(_model.device)

        with torch.no_grad():
            output_ids = _model.generate(**inputs, max_new_tokens=8192)
        trimmed = output_ids[:, inputs["input_ids"].shape[1]:]
        response = _processor.batch_decode(trimmed, skip_special_tokens=True)[0]

        return _parse_detection_response(response)
    except Exception as exc:
        log.error("Detection failed: %s", exc)
        return {**_empty, "error": True}
    finally:
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass


def unload_model() -> None:
    """Qwen-Modell und Prozessor aus dem VRAM entladen."""
    global _model, _processor
    import gc
    _model = None
    _processor = None
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass
    log.info("VLM model unloaded from GPU.")

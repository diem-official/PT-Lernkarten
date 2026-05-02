import json
import logging
import re

from PIL import Image

log = logging.getLogger("vlm_classify")

_SYSTEM_PROMPT = (
    "You are an anatomical terminology expert. "
    "Respond ONLY with a JSON object — no prose, no markdown fences."
)

_TERM_PROMPT = (
    "You are given an anatomical diagram with red bounding boxes around text regions. "
    "Read every anatomical label visible in the image. "
    "Reconstruct complete multi-line terms (e.g. 'Apex' + 'ossis' + 'sacri' → "
    "'Apex ossis sacri'), fix hyphenated line breaks "
    "(e.g. 'Promon-' + 'torium' → 'Promontorium'), and correct obvious OCR artifacts. "
    "Ignore non-anatomical watermarks and artist signatures. "
    "Return ONLY this JSON object — no prose, no markdown fences:\n"
    '{"terms": ["Ala ossis sacri", "Promontorium", "Apex ossis sacri"]}'
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
    proc = AutoProcessor.from_pretrained(model_id)
    mdl = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    mdl.eval()
    _processor, _model = proc, mdl
    log.info("Model loaded.")


def _run_vlm(image: Image.Image, prompt: str) -> str:
    """Single VLM inference pass — returns the raw response string."""
    from qwen_vl_utils import process_vision_info
    import torch

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt},
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
    return _processor.batch_decode(trimmed, skip_special_tokens=True)[0]


def _extract_json(text: str, context: str) -> dict | None:
    """Extract the first JSON object from a raw VLM response string."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        log.warning("VLM %s: no JSON object found in response", context)
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        log.warning("VLM %s: JSON parse failure", context)
        return None


def _parse_terms_response(text: str) -> list[str]:
    """Parse VLM response → list of anatomical term strings."""
    data = _extract_json(text, "terms")
    if data is None:
        return []
    terms = []
    for t in data.get("terms", []):
        if isinstance(t, str) and t.strip():
            terms.append(t.strip())
    return terms


def detect_labels(image: Image.Image, ocr_blocks: list[dict]) -> dict:
    """
    Single-pass VLM term extraction.
    ocr_blocks is used only as a presence guard; the VLM reads labels directly from the image.
    Returns {"terms": ["Term 1", ...]} or {"terms": [], "error": True} on failure.
    """
    _empty: dict = {"terms": []}
    if not ocr_blocks:
        return _empty
    try:
        _load_model()
        log.info("VLM pass: extracting anatomical terms from image")
        response = _run_vlm(image, _TERM_PROMPT)
        terms = _parse_terms_response(response)
        log.info("VLM extracted %d term(s): %s", len(terms), terms)
        return {"terms": terms}
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

import json
import logging
import re
from typing import Any

from PIL import Image

log = logging.getLogger("vlm_classify")

_UMLAUT_MAP = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
})

_VALID_CATEGORIES = {
    "Knochen", "Muskeln", "Gelenke", "Bänder", "Gefäße", "Nerven", "Organe"
}

_SYSTEM_PROMPT = (
    "You are an anatomy atlas classifier. "
    "Respond ONLY with a JSON object — no prose, no markdown fences."
)

_USER_PROMPT = (
    "Look at this image. Return a JSON object with these keys:\n"
    "- is_anatomical (bool): true if this is an anatomical diagram containing pointer lines or labels\n"
    "- category (str or null): one of Knochen, Muskeln, Gelenke, Bänder, Gefäße, Nerven, Organe\n"
    "- subcategory (str or null): e.g. Arm, Bein, Kopf, Rumpf, Becken, Hand, Fuß, Schulter, Hüfte\n"
    "- view (str or null): e.g. dorsal, ventral, lateral, medial, frontal, superior, inferior\n"
    "If is_anatomical is false, set the other fields to null."
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


def _generate_response(image: Image.Image) -> str:
    """Run inference and return the raw text response."""
    _load_model()
    from qwen_vl_utils import process_vision_info

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": _USER_PROMPT},
            ],
        },
    ]
    text = _processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = _processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    ).to(_model.device)

    import torch
    with torch.no_grad():
        output_ids = _model.generate(**inputs, max_new_tokens=256)
    trimmed = output_ids[:, inputs["input_ids"].shape[1]:]
    return _processor.batch_decode(trimmed, skip_special_tokens=True)[0]


def _parse_response(text: str) -> tuple[dict | None, str]:
    """Parse VLM text → (classification_dict, reason). reason is '' on success."""
    # Step 1-2: extract and parse JSON
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None, "json parse failure"
    try:
        data: dict[str, Any] = json.loads(match.group())
    except json.JSONDecodeError:
        return None, "json parse failure"

    # Step 3: is_anatomical
    if "is_anatomical" not in data:
        return None, "missing field: is_anatomical"
    val = data["is_anatomical"]
    if val is not True and str(val) not in ("true", "True"):
        return None, "not anatomical"

    # Step 4: required fields present and non-empty
    for field in ("category", "subcategory", "view"):
        if not data.get(field):
            return None, f"missing field: {field}"

    # Step 5: normalise — strip, title-case cat/sub, lowercase view
    category = data["category"].strip().title()
    subcategory = data["subcategory"].strip().title()
    view = data["view"].strip().lower()

    # Step 6: validate category (after title-case, before transliteration)
    if category not in _VALID_CATEGORIES:
        return None, f"unknown category: {category}"

    # Step 7: transliterate Umlauts, replace spaces
    category = category.translate(_UMLAUT_MAP).replace(" ", "_")
    subcategory = subcategory.translate(_UMLAUT_MAP).replace(" ", "_")
    view = view.translate(_UMLAUT_MAP).replace(" ", "_")

    return {"category": category, "subcategory": subcategory, "view": view}, ""


def classify(image: Image.Image) -> tuple[dict | None, str]:
    """
    Returns (result, reason).
    result is {"category": str, "subcategory": str, "view": str} on success, else None.
    reason is "" when result is not None.
    """
    try:
        raw = _generate_response(image)
        return _parse_response(raw)
    except Exception as exc:
        return None, f"model error: {exc}"

import json
import logging
import re

from PIL import Image

log = logging.getLogger("vlm_classify")

_SYSTEM_PROMPT = (
    "You are an anatomical terminology expert and image quality inspector. "
    "Respond ONLY with a JSON object — no prose, no markdown fences."
)

_FILTER_PROMPT = (
    "I will give you a JSON list of OCR text blocks extracted from an anatomical diagram. "
    "The image shows RED bounding boxes around each detected OCR region. "
    "Each block has an 'id' and a 'text' field.\n\n"
    "Your ONLY task: identify which block IDs are NOT real text labels. "
    "Flag blocks that are pointer-line artifacts, stray dots, isolated dashes, lone "
    "punctuation marks, or any other non-textual mark mistakenly detected by OCR.\n\n"
    "Return ONLY this JSON object — no prose, no markdown fences:\n"
    '{"invalid_ocr_ids": [3, 7]}'
)

_GROUPING_PROMPT = (
    "I will give you a JSON list of OCR text blocks extracted from an anatomical diagram. "
    "Every block in this list has already been verified as real text — there is no noise. "
    "The image shows RED bounding boxes around each block.\n\n"
    "Your task: reconstruct every complete anatomical term by grouping the block IDs that "
    "belong together. A single term may span multiple lines and therefore multiple blocks "
    "(e.g. 'Apex' + 'ossis' + 'sacri' → 'Apex ossis sacri'). "
    "Fix hyphenated split words (e.g. 'Promon-' + 'torium' → 'Promontorium') and obvious "
    "OCR typos. Ignore non-anatomical watermarks and artist signatures.\n\n"
    "STRICT COMPLETENESS RULE: Every ID in the input MUST appear in exactly one grouping's "
    "'ocr_ids'. It is forbidden to skip or omit any ID. Before responding, verify that "
    "the union of all 'ocr_ids' across all groupings equals the complete input ID set.\n\n"
    "Also set missing_words_detected to true if you can see anatomical label text in the "
    "image that has NO red bounding box around it.\n\n"
    "Return ONLY this JSON object — no prose, no markdown fences:\n"
    '{"groupings": [{"term": "Apex ossis sacri", "ocr_ids": [5, 6, 7]}], '
    '"missing_words_detected": false}'
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


def _parse_filter_response(text: str) -> list[int]:
    """Parse Pass 1 filter response → list of invalid OCR IDs."""
    data = _extract_json(text, "filter")
    if data is None:
        return []
    invalid = []
    for i in data.get("invalid_ocr_ids", []):
        try:
            invalid.append(int(i))
        except (TypeError, ValueError):
            continue
    return invalid


def _parse_grouping_response(text: str, valid_ids: set[int]) -> dict:
    """Parse Pass 2 grouping response → groupings + missing_words_detected."""
    _empty = {"groupings": [], "missing_words_detected": False}
    data = _extract_json(text, "grouping")
    if data is None:
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

    covered = {i for g in groupings for i in g["ocr_ids"]}
    omitted = valid_ids - covered
    if omitted:
        log.warning("VLM grouping omitted %d ID(s): %s", len(omitted), sorted(omitted))

    missing = bool(data.get("missing_words_detected", False))
    return {"groupings": groupings, "missing_words_detected": missing}


def detect_labels(image: Image.Image, ocr_blocks: list[dict]) -> dict:
    """
    Two-pass VLM grouping.
    Pass 1 (_FILTER_PROMPT):  identifies artifact/noise IDs → invalid_ocr_ids
    Pass 2 (_GROUPING_PROMPT): groups verified-valid blocks → groupings, missing_words_detected
    Returns {"groupings": [...], "invalid_ocr_ids": [...], "missing_words_detected": bool}.
    On any error returns the empty/safe version of that dict.
    """
    _empty: dict = {"groupings": [], "invalid_ocr_ids": [], "missing_words_detected": False}
    if not ocr_blocks:
        return _empty
    try:
        _load_model()

        # ── Pass 1: artifact filter ──────────────────────────────────────────
        ocr_json = json.dumps(
            [{"id": b["id"], "text": b["text"]} for b in ocr_blocks],
            ensure_ascii=False,
        )
        log.info("Pass 1 (filter): %d OCR blocks", len(ocr_blocks))
        response1 = _run_vlm(image, _FILTER_PROMPT + "\n\nOCR blocks:\n" + ocr_json)
        invalid_ocr_ids = _parse_filter_response(response1)
        invalid_id_set = set(invalid_ocr_ids)
        log.info("Pass 1 result: %d invalid ID(s): %s", len(invalid_ocr_ids), sorted(invalid_ocr_ids))

        # ── Intermediate: keep only verified-valid blocks ────────────────────
        valid_blocks = [b for b in ocr_blocks if b["id"] not in invalid_id_set]
        if not valid_blocks:
            log.warning("All OCR blocks were filtered as invalid — skipping grouping pass")
            return {"groupings": [], "invalid_ocr_ids": invalid_ocr_ids, "missing_words_detected": False}

        # ── Pass 2: semantic grouping ────────────────────────────────────────
        valid_json = json.dumps(
            [{"id": b["id"], "text": b["text"]} for b in valid_blocks],
            ensure_ascii=False,
        )
        valid_id_set = {b["id"] for b in valid_blocks}
        log.info("Pass 2 (grouping): %d valid blocks", len(valid_blocks))
        response2 = _run_vlm(image, _GROUPING_PROMPT + "\n\nOCR blocks:\n" + valid_json)
        grouping_result = _parse_grouping_response(response2, valid_id_set)

        # ── Orphan Rescue: all valid_blocks are verified real text, so any ID
        #    that Pass 2 forgot is a genuine anatomical term — rescue directly.
        covered = {i for g in grouping_result["groupings"] for i in g["ocr_ids"]}
        orphan_ids = valid_id_set - covered
        if orphan_ids:
            text_by_id = {b["id"]: b["text"] for b in valid_blocks}
            rescued = []
            for oid in sorted(orphan_ids):
                grouping_result["groupings"].append({
                    "term": text_by_id.get(oid, ""),
                    "ocr_ids": [oid],
                })
                rescued.append((oid, text_by_id.get(oid, "")))
            log.warning(
                "Orphan Rescue: rescued %d block(s) forgotten by Pass 2: %s",
                len(rescued),
                rescued,
            )

        return {
            "groupings": grouping_result["groupings"],
            "invalid_ocr_ids": invalid_ocr_ids,
            "missing_words_detected": grouping_result["missing_words_detected"],
        }
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

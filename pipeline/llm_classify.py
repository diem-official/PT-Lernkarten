# pipeline/llm_classify.py
import json
import logging
import re

log = logging.getLogger("llm_classify")

_SYSTEM_PROMPT = (
    "You are an anatomical terminology expert and OCR-stitching assistant. "
    "Respond ONLY with a valid JSON object. Do not include markdown formatting or explanations."
)

_PROMPT_TEMPLATE = (
    "Category: {category}, Subcategory: {subcategory}\n\n"
    "Below is a complete list of OCR blocks from an anatomical diagram. "
    "Some long anatomical terms were split into multiple boxes due to line breaks. "
    "Your task is to reconstruct ALL complete anatomical terms.\n"
    "Rules:\n"
    "1. Merge blocks that semantically form a complete anatomical term AND are spatially close to each other (check x, y coordinates).\n"
    "2. If a single block is a complete term, keep it as is.\n"
    "3. Correct minor typos if obvious.\n"
    "4. Return every single valid label present in the input.\n\n"
    "Return a JSON object with a single key 'terms', which is a list of objects. "
    "Each object must have a 'name' (the reconstructed term) and 'ids' (a list of the original integer IDs used).\n\n"
    "Blocks:\n{blocks_json}"
)

_model = None
_tokenizer = None


def _load_model() -> None:
    global _model, _tokenizer
    if _model is not None:
        return
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    log.info("Loading Qwen2.5-7B-Instruct …")
    model_id = "Qwen/Qwen2.5-7B-Instruct"
    tok = AutoTokenizer.from_pretrained(model_id)
    mdl = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    mdl.eval()
    _tokenizer, _model = tok, mdl
    log.info("Text LLM loaded.")


def _extract_json(text: str, context: str) -> dict | None:
    """Extract the first JSON object from a raw LLM response string."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        log.warning("LLM %s: no JSON object found in response", context)
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        log.warning("LLM %s: JSON parse failure", context)
        return None


def detect_labels(ocr_blocks: list[dict], category: str = "Unknown", subcategory: str = "Unknown") -> dict:
    """
    Single-pass LLM term extraction — all blocks processed in one call.
    Returns {"terms": [{"name": str, "ids": [int, ...]}, ...]}
    or {"terms": [], "error": True} on hard failure.
    """
    if not ocr_blocks:
        return {"terms": []}
    try:
        import torch
        _load_model()

        minimal_blocks = [
            {"id": b["id"], "text": b["text"], "x": b["x"], "y": b["y"]}
            for b in ocr_blocks
        ]
        blocks_json = json.dumps(minimal_blocks, ensure_ascii=False)

        prompt = _PROMPT_TEMPLATE.format(
            category=category,
            subcategory=subcategory,
            blocks_json=blocks_json,
        )
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ]
        text_input = _tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = _tokenizer(text_input, return_tensors="pt").to(_model.device)
        log.info("LLM single-pass: %d blocks → one inference call", len(ocr_blocks))
        with torch.no_grad():
            output_ids = _model.generate(**inputs, max_new_tokens=4096)
        trimmed = output_ids[:, inputs["input_ids"].shape[1]:]
        raw_output = _tokenizer.batch_decode(trimmed, skip_special_tokens=True)[0]

        parsed = _extract_json(raw_output, "single_pass")
        if parsed is None or "terms" not in parsed:
            log.warning("LLM failed to output valid 'terms' array.")
            return {"terms": [], "error": True}

        terms = [
            {"name": t["name"].strip(), "ids": t["ids"]}
            for t in parsed["terms"]
            if isinstance(t, dict)
            and isinstance(t.get("name"), str)
            and t["name"].strip()
            and isinstance(t.get("ids"), list)
        ]
        log.info("LLM single-pass: %d term(s) extracted", len(terms))
        return {"terms": terms}

    except Exception as exc:
        log.error("Detection failed: %s", exc)
        return {"terms": [], "error": True}
    finally:
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass


def unload_model() -> None:
    """Release model and tokenizer from GPU memory."""
    global _model, _tokenizer
    import gc
    _model = None
    _tokenizer = None
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass
    log.info("LLM model unloaded from GPU.")

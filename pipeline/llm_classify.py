# pipeline/llm_classify.py
import collections
import json
import logging
import re

log = logging.getLogger("llm_classify")

_SYSTEM_PROMPT = (
    "You are an anatomical terminology expert. "
    "Respond ONLY with a JSON object — no prose, no markdown fences."
)

_BUNDLE_PROMPT_TEMPLATE = (
    "You are given a list of OCR text blocks from an anatomical diagram, "
    "each with a numeric id and a text fragment. "
    "Group consecutive fragments that together form a single anatomical term "
    "(e.g. multi-line labels, hyphenated line-breaks). "
    "Fix obvious OCR errors (e.g. 'M.' for 'Musculus'). "
    "A bundle may contain multiple independent terms. "
    "Return ONLY this JSON object — no prose, no markdown fences:\n"
    '{{"terms": [{{"name": "M. biceps brachii", "ids": [0, 1, 2]}}]}}\n\n'
    "Blocks:\n{blocks_json}"
)

_model = None
_tokenizer = None


def _group_bundles(ocr_blocks: list[dict]) -> list[list[dict]]:
    """
    For each block as anchor: collect all blocks whose y is in
    [anchor.y, anchor.y + 10*anchor.h] AND whose x-range overlaps.
    Each bundle is sorted by ascending y.  Returns one bundle per anchor.
    """
    bundles: list[list[dict]] = []
    for anchor in ocr_blocks:
        ay, ah = anchor["y"], anchor["h"]
        ax, aw = anchor["x"], anchor["w"]
        y_max = ay + 10 * ah
        bundle = [
            b for b in ocr_blocks
            if ay <= b["y"] <= y_max
            and b["x"] < ax + aw
            and b["x"] + b["w"] > ax
        ]
        bundle.sort(key=lambda b: b["y"])
        bundles.append(bundle)
    return bundles


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


def _run_llm(bundle: list[dict]) -> str:
    """Single LLM inference for one bundle.  Returns raw response string."""
    import torch

    blocks_json = json.dumps(
        [{"id": b["id"], "text": b["text"]} for b in bundle],
        ensure_ascii=False,
    )
    prompt = _BUNDLE_PROMPT_TEMPLATE.format(blocks_json=blocks_json)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]
    text_input = _tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = _tokenizer(text_input, return_tensors="pt").to(_model.device)
    with torch.no_grad():
        output_ids = _model.generate(**inputs, max_new_tokens=512)
    trimmed = output_ids[:, inputs["input_ids"].shape[1]:]
    return _tokenizer.batch_decode(trimmed, skip_special_tokens=True)[0]


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


def _parse_bundle_response(text: str) -> list[dict]:
    """Parse LLM response into list of {"name": str, "ids": [int]} dicts."""
    data = _extract_json(text, "bundle")
    if data is None:
        return []
    result = []
    for t in data.get("terms", []):
        if (
            isinstance(t, dict)
            and isinstance(t.get("name"), str)
            and t["name"].strip()
            and isinstance(t.get("ids"), list)
            and all(isinstance(i, int) for i in t["ids"])
        ):
            result.append({"name": t["name"].strip(), "ids": t["ids"]})
    return result


def _vote_terms(
    all_responses: list[list[dict]],
    min_votes: int = 3,
) -> list[dict]:
    """
    Consensus vote across all bundle LLM responses.
    Key = tuple(sorted(ids)).  Accept signatures with >= min_votes.
    Name = most-voted name for accepted signatures.
    """
    vote_counts: collections.Counter = collections.Counter()
    name_votes: dict[tuple, collections.Counter] = collections.defaultdict(collections.Counter)

    for response in all_responses:
        for term in response:
            sig = tuple(sorted(term["ids"]))
            vote_counts[sig] += 1
            name_votes[sig][term["name"]] += 1

    results = []
    for sig, count in vote_counts.items():
        if count >= min_votes:
            best_name = name_votes[sig].most_common(1)[0][0]
            results.append({"name": best_name, "ids": list(sig)})
    return results


def detect_labels(ocr_blocks: list[dict]) -> dict:
    """
    Text-LLM term extraction with consensus voting.
    Returns {"terms": [{"name": str, "ids": [int, ...]}, ...]}
    or {"terms": [], "error": True} on hard failure.
    """
    if not ocr_blocks:
        return {"terms": []}
    try:
        _load_model()
        bundles = _group_bundles(ocr_blocks)
        log.info("LLM pass: %d bundles to classify", len(bundles))
        all_responses: list[list[dict]] = []
        for bundle in bundles:
            raw = _run_llm(bundle)
            parsed = _parse_bundle_response(raw)
            all_responses.append(parsed)
        terms = _vote_terms(all_responses)
        log.info("LLM consensus: %d term(s) accepted", len(terms))
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

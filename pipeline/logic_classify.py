import logging

log = logging.getLogger("logic_classify")

# Vertical gap tolerance: successor's top may be at most this fraction of A's height below A's bottom.
_GAP_RATIO = 0.20
# Alignment tolerance: left or right edge must match within this fraction of A's width.
_ALIGN_RATIO = 0.05
# Minimum absolute alignment tolerance in pixels (guards against very narrow blocks).
_ALIGN_MIN_PX = 3


def detect_labels(ocr_blocks: list[dict], **_kwargs) -> dict:
    """
    Deterministic graph-based term extraction.

    Each block finds its best successor — the nearest block below it whose
    left or right edge is flush-aligned. Chains of linked blocks form one term.

    Returns {"terms": [{"name": str, "ids": [int, ...]}, ...]}
    """
    if not ocr_blocks:
        return {"terms": []}

    sorted_blocks = sorted(ocr_blocks, key=lambda b: b["y"])

    # Build successor map: block_id -> best_successor_id (or None)
    successor: dict[int, int | None] = {b["id"]: None for b in sorted_blocks}

    for i, a in enumerate(sorted_blocks):
        a_bottom = a["y"] + a["h"]
        a_left = a["x"]
        a_right = a["x"] + a["w"]
        max_gap = _GAP_RATIO * a["h"]
        align_tol = max(_ALIGN_MIN_PX, _ALIGN_RATIO * a["w"])

        best_id: int | None = None
        best_gap = float("inf")

        for b in sorted_blocks[i + 1:]:
            if b["y"] <= a["y"]:
                continue

            gap = b["y"] - a_bottom
            if gap > max_gap:
                continue

            b_left = b["x"]
            b_right = b["x"] + b["w"]
            if abs(b_left - a_left) > align_tol and abs(b_right - a_right) > align_tol:
                continue

            if gap < best_gap:
                best_gap = gap
                best_id = b["id"]

        successor[a["id"]] = best_id

    # Blocks pointed to by a successor are not chain roots.
    has_predecessor = {v for v in successor.values() if v is not None}
    block_by_id = {b["id"]: b for b in sorted_blocks}
    claimed: set[int] = set()
    terms: list[dict] = []

    for block in sorted_blocks:
        bid = block["id"]
        if bid in has_predecessor or bid in claimed:
            continue

        chain: list[dict] = []
        cur: int | None = bid
        while cur is not None and cur not in claimed:
            claimed.add(cur)
            chain.append(block_by_id[cur])
            cur = successor[cur]

        terms.append({
            "name": " ".join(b["text"] for b in chain),
            "ids": [b["id"] for b in chain],
        })

    log.info("logic_classify: %d block(s) → %d term(s)", len(ocr_blocks), len(terms))
    return {"terms": terms}


def unload_model() -> None:
    """No-op: deterministic classifier has no model to unload."""
    pass

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from logic_classify import detect_labels


def _blk(id_, x, y, w, h, text="X"):
    return {"id": id_, "text": text, "x": x, "y": y, "w": w, "h": h}


def test_empty_input_returns_empty():
    assert detect_labels([]) == {"terms": []}


def test_single_block_becomes_single_term():
    blocks = [_blk(0, x=10, y=10, w=80, h=20, text="Femur")]
    result = detect_labels(blocks)
    assert len(result["terms"]) == 1
    assert result["terms"][0]["name"] == "Femur"
    assert result["terms"][0]["ids"] == [0]


def test_two_left_aligned_blocks_with_small_gap_are_merged():
    # A bottom=30, B top=33, gap=3, max_gap=0.2*20=4 → within limit
    a = _blk(0, x=10, y=10, w=80, h=20, text="M. biceps")
    b = _blk(1, x=10, y=33, w=80, h=20, text="brachii")
    result = detect_labels([a, b])
    assert len(result["terms"]) == 1
    assert result["terms"][0]["name"] == "M. biceps brachii"
    assert sorted(result["terms"][0]["ids"]) == [0, 1]


def test_two_left_aligned_blocks_with_large_gap_stay_separate():
    # A bottom=30, B top=60, gap=30, max_gap=0.2*20=4 → too large
    a = _blk(0, x=10, y=10, w=80, h=20, text="Femur")
    b = _blk(1, x=10, y=60, w=80, h=20, text="Humerus")
    result = detect_labels([a, b])
    assert len(result["terms"]) == 2


def test_two_right_aligned_blocks_are_merged():
    # A: x=10, w=80 → right=90; B: x=30, w=60 → right=90, left differs
    # gap: A bottom=30, B top=32 → gap=2 ≤ 0.2*20=4
    a = _blk(0, x=10, y=10, w=80, h=20, text="Part1")
    b = _blk(1, x=30, y=32, w=60, h=20, text="Part2")
    result = detect_labels([a, b])
    assert len(result["terms"]) == 1
    assert result["terms"][0]["name"] == "Part1 Part2"


def test_non_aligned_blocks_stay_separate():
    # A right=90, B left=100, right=160 — no edge match
    a = _blk(0, x=10, y=10, w=80, h=20, text="Alpha")
    b = _blk(1, x=100, y=33, w=60, h=20, text="Beta")
    result = detect_labels([a, b])
    assert len(result["terms"]) == 2


def test_overlap_negative_gap_is_valid():
    # A bottom=30, B top=25 → gap=-5 (overlap), which is ≤ max_gap=4 → merge
    a = _blk(0, x=10, y=10, w=80, h=20, text="Linea")
    b = _blk(1, x=10, y=25, w=80, h=20, text="alba")
    result = detect_labels([a, b])
    assert len(result["terms"]) == 1
    assert result["terms"][0]["name"] == "Linea alba"


def test_three_block_chain():
    # All left-aligned, gaps within 20% of 20px each
    a = _blk(0, x=10, y=10, w=80, h=20, text="M.")
    b = _blk(1, x=10, y=33, w=80, h=20, text="biceps")
    c = _blk(2, x=10, y=56, w=80, h=20, text="brachii")
    result = detect_labels([a, b, c])
    assert len(result["terms"]) == 1
    assert result["terms"][0]["name"] == "M. biceps brachii"
    assert sorted(result["terms"][0]["ids"]) == [0, 1, 2]


def test_two_independent_terms_extracted():
    # Two independent left-aligned chains, far apart horizontally
    a0 = _blk(0, x=10,  y=10, w=80, h=20, text="Femur")
    a1 = _blk(1, x=10,  y=33, w=80, h=20, text="links")
    b0 = _blk(2, x=300, y=10, w=80, h=20, text="Humerus")
    b1 = _blk(3, x=300, y=33, w=80, h=20, text="rechts")
    result = detect_labels([a0, a1, b0, b1])
    assert len(result["terms"]) == 2
    names = {t["name"] for t in result["terms"]}
    assert names == {"Femur links", "Humerus rechts"}


def test_nearest_candidate_wins_tie():
    # A (x=10, w=100) has two valid candidates in gap range:
    #   b1 is left-aligned with A (gap=2), b2 is right-aligned with A (gap=3).
    #   b1 and b2 share no common edge → b1 cannot chain into b2.
    # Expected: A→b1, b2 is its own term.
    a  = _blk(0, x=10, y=10, w=100, h=20, text="A")   # right=110, max_gap=4
    b1 = _blk(1, x=10, y=32, w=50,  h=20, text="near")  # left-aligned, gap=2
    b2 = _blk(2, x=60, y=33, w=50,  h=20, text="far")   # right-aligned (60+50=110), gap=3
    result = detect_labels([a, b1, b2])
    term_for_a = next(t for t in result["terms"] if 0 in t["ids"])
    assert 1 in term_for_a["ids"]   # b1 chosen (nearest)
    assert 2 not in term_for_a["ids"]  # b2 is its own term


def test_unload_model_is_noop():
    from logic_classify import unload_model
    unload_model()  # must not raise

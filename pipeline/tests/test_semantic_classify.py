import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import math
import numpy as np
import pytest
from semantic_classify import OcrNode, AssociationEdge


# ── OcrNode ──────────────────────────────────────────────────────────────────

def test_ocr_node_creation():
    node = OcrNode(id=1, text="Femur", coords=(10, 20, 110, 40))
    assert node.line_height == 20
    assert node.leader_line_id is None
    assert node.nlp_features == {}

def test_ocr_node_derived_properties():
    node = OcrNode(id=2, text="M.", coords=(5, 10, 55, 30))
    assert node.xmin == 5
    assert node.ymin == 10
    assert node.xmax == 55
    assert node.ymax == 30
    assert node.width == 50
    assert node.line_height == 20


# ── AssociationEdge ───────────────────────────────────────────────────────────

def test_association_edge_total_weight():
    n1 = OcrNode(id=1, text="M.", coords=(0, 0, 50, 20))
    n2 = OcrNode(id=2, text="biceps", coords=(0, 25, 80, 45))
    edge = AssociationEdge(source_node=n1, target_node=n2,
                           geo_score=0.8, cv_score=0.0, nlp_score=1.0)
    assert abs(edge.total_weight - 1.8) < 0.001

def test_association_edge_cv_veto():
    n1 = OcrNode(id=1, text="A", coords=(0, 0, 50, 20))
    n2 = OcrNode(id=2, text="B", coords=(0, 25, 50, 45))
    edge = AssociationEdge(source_node=n1, target_node=n2,
                           geo_score=0.9, cv_score=float('-inf'), nlp_score=1.0)
    assert edge.total_weight == float('-inf')


from semantic_classify import _ingest


# ── Module 1: _ingest ─────────────────────────────────────────────────────────

def test_ingest_converts_blocks_to_nodes():
    blocks = [
        {"id": 0, "text": "Femur", "x": 10, "y": 20, "w": 100, "h": 20},
        {"id": 1, "text": "links",  "x": 10, "y": 45, "w": 80,  "h": 18},
    ]
    nodes, avg_h = _ingest(blocks)
    assert len(nodes) == 2
    assert nodes[0].coords == (10, 20, 110, 40)   # x, y, x+w, y+h
    assert nodes[0].text == "Femur"
    assert nodes[1].coords == (10, 45, 90, 63)

def test_ingest_computes_average_height():
    blocks = [
        {"id": 0, "text": "A", "x": 0, "y": 0,  "w": 50, "h": 20},
        {"id": 1, "text": "B", "x": 0, "y": 30, "w": 50, "h": 30},
    ]
    _, avg_h = _ingest(blocks)
    assert avg_h == 25.0

def test_ingest_empty():
    nodes, avg_h = _ingest([])
    assert nodes == []
    assert avg_h == 0.0


from semantic_classify import _geometric_edges


# ── Module 2: _geometric_edges ───────────────────────────────────────────────

def _gnode(id_, x, y, w, h, text="X"):
    return OcrNode(id=id_, text=text, coords=(x, y, x + w, y + h))

def test_geo_left_aligned_creates_edge():
    a = _gnode(0, 10, 0,  100, 20)   # bottom=20
    b = _gnode(1, 10, 25, 80,  18)   # top=25; gap=5; max_gap=0.6*avg_h
    edges = _geometric_edges([a, b], avg_height=20.0)
    assert len(edges) == 1
    assert edges[0].source_node is a
    assert edges[0].target_node is b
    assert edges[0].geo_score > 0.0

def test_geo_large_gap_no_edge():
    a = _gnode(0, 10, 0,  100, 20)
    b = _gnode(1, 10, 60, 80,  18)   # gap=40 >> 0.6*20=12
    assert _geometric_edges([a, b], 20.0) == []

def test_geo_right_aligned_creates_edge():
    a = _gnode(0, 10, 0,  100, 20)   # right=110
    b = _gnode(1, 30, 25, 80,  18)   # right=110; left mismatched but right matches
    edges = _geometric_edges([a, b], 20.0)
    assert len(edges) == 1

def test_geo_misaligned_no_edge():
    a = _gnode(0, 10, 0,  100, 20)
    b = _gnode(1, 50, 25, 40,  18)   # left diff=40, right diff=20; tol=max(3,5)=5
    assert _geometric_edges([a, b], 20.0) == []

def test_geo_center_aligned_creates_edge():
    # a: x=10, w=100 → center=60; b: x=30, w=60 → center=60
    a = _gnode(0, 10, 0,  100, 20)
    b = _gnode(1, 30, 25, 60,  18)
    edges = _geometric_edges([a, b], 20.0)
    assert len(edges) == 1

def test_geo_negative_gap_is_valid():
    # Slight overlap (b starts before a ends)
    a = _gnode(0, 10, 0,  80, 20)    # bottom=20
    b = _gnode(1, 10, 15, 80, 18)   # top=15; gap=-5 (overlap)
    assert len(_geometric_edges([a, b], 20.0)) == 1

def test_geo_score_is_positive_float():
    a = _gnode(0, 10, 0, 100, 20)
    b = _gnode(1, 10, 22, 80, 18)
    edges = _geometric_edges([a, b], 20.0)
    assert 0.0 < edges[0].geo_score <= 1.5

def test_geo_narrow_short_word_tolerates_ocr_jitter():
    # Regression: "Lig." (80px wide) followed by "collaterale", left edges
    # 5px apart — real OCR bbox jitter between narrow and wide glyphs that
    # must still count as left-aligned (values taken from a real misfire).
    a = _gnode(0, 1457, 1666, 80, 59, text="Lig.")
    b = _gnode(1, 1462, 1719, 194, 46, text="collaterale")
    edges = _geometric_edges([a, b], avg_height=58.8)
    assert len(edges) == 1


from semantic_classify import _nlp_score


# ── Module 4: _nlp_score ─────────────────────────────────────────────────────

def _nnode(text):
    return OcrNode(id=0, text=text, coords=(0, 0, 60, 20))

def test_nlp_abbreviation_forces_merge():
    for abbrev in ["M.", "Mm.", "A.", "V.", "N.", "Lig.", "R."]:
        assert _nlp_score(_nnode(abbrev), _nnode("test")) >= 1.5, abbrev

def test_nlp_two_known_nouns_veto():
    assert _nlp_score(_nnode("Femur"), _nnode("Tibia")) <= -0.5

def test_nlp_noun_adjective_positive():
    # "Facies" (noun) + "articularis" (lowercase adj ending in -is)
    assert _nlp_score(_nnode("Facies"), _nnode("articularis")) > 0.0

def test_nlp_unknown_pair_neutral():
    score = _nlp_score(_nnode("xyz"), _nnode("abc"))
    assert -0.1 <= score <= 0.1


from semantic_classify import _assign_leader_lines, _cv_score_for_edge


# ── Module 3: CV leader lines ─────────────────────────────────────────────────

def test_cv_no_leader_map_neutral():
    n1 = OcrNode(id=0, text="A", coords=(10, 10, 60, 30))
    n2 = OcrNode(id=1, text="B", coords=(10, 35, 60, 55))
    edge = AssociationEdge(source_node=n1, target_node=n2)
    assert _cv_score_for_edge(edge, {}) == 0.0

def test_cv_same_leader_positive():
    n1 = OcrNode(id=0, text="A", coords=(10, 10, 60, 30))
    n2 = OcrNode(id=1, text="B", coords=(10, 35, 60, 55))
    edge = AssociationEdge(source_node=n1, target_node=n2)
    assert _cv_score_for_edge(edge, {0: "L0", 1: "L0"}) == 2.0

def test_cv_different_leaders_veto():
    n1 = OcrNode(id=0, text="A", coords=(10, 10, 60, 30))
    n2 = OcrNode(id=1, text="B", coords=(10, 35, 60, 55))
    edge = AssociationEdge(source_node=n1, target_node=n2)
    result = _cv_score_for_edge(edge, {0: "L0", 1: "L1"})
    assert math.isinf(result) and result < 0

def test_cv_assign_returns_dict():
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[20:80, 50] = 255   # vertical white line at x=50
    nodes = [
        OcrNode(id=0, text="A", coords=(45, 5,  55, 15)),
        OcrNode(id=1, text="B", coords=(45, 20, 55, 30)),
        OcrNode(id=2, text="C", coords=(80, 5,  90, 15)),  # far from line
    ]
    leader_map = _assign_leader_lines(img, nodes)
    assert isinstance(leader_map, dict)
    assert set(leader_map.keys()) <= {n.id for n in nodes}


from semantic_classify import _fuse_graph, _super_bbox


# ── Module 5: _fuse_graph + _super_bbox ─────────────────────────────────────

def test_single_node_one_term():
    node = OcrNode(id=0, text="Femur", coords=(10, 10, 110, 30))
    assert _fuse_graph([node], []) == [[node]]

def test_two_nodes_merge_on_high_weight():
    a = OcrNode(id=0, text="M.",      coords=(10,  0, 60, 20))
    b = OcrNode(id=1, text="biceps",  coords=(10, 25, 90, 45))
    edge = AssociationEdge(a, b, geo_score=0.9, nlp_score=1.5)
    groups = _fuse_graph([a, b], [edge])
    assert len(groups) == 1
    assert set(groups[0]) == {a, b}

def test_veto_keeps_separate():
    a = OcrNode(id=0, text="Femur", coords=(10,  0, 110, 20))
    b = OcrNode(id=1, text="Tibia", coords=(10, 25, 110, 45))
    edge = AssociationEdge(a, b, geo_score=0.9, cv_score=float('-inf'))
    assert len(_fuse_graph([a, b], [edge])) == 2

def test_groups_sorted_by_y():
    a = OcrNode(id=0, text="brachii", coords=(10, 40, 100, 60))
    b = OcrNode(id=1, text="M.",      coords=(10,  0,  50, 20))
    c = OcrNode(id=2, text="biceps",  coords=(10, 22,  90, 42))
    edges = [
        AssociationEdge(b, c, geo_score=0.9, nlp_score=1.5),
        AssociationEdge(c, a, geo_score=0.8),
    ]
    groups = _fuse_graph([a, b, c], edges)
    assert len(groups) == 1
    assert [n.text for n in groups[0]] == ["M.", "biceps", "brachii"]

def test_super_bbox():
    a = OcrNode(id=0, text="M.",    coords=(10,  0, 50, 20))
    b = OcrNode(id=1, text="biceps", coords=( 5, 25, 90, 45))
    assert _super_bbox([a, b]) == (5, 0, 90, 45)


from semantic_classify import detect_labels


# ── Public API ───────────────────────────────────────────────────────────────

def test_detect_labels_empty():
    assert detect_labels([]) == {"terms": []}

def test_detect_labels_abbreviation_merges():
    blocks = [
        {"id": 0, "text": "M.",     "x": 10, "y":  0, "w": 30, "h": 20},
        {"id": 1, "text": "biceps", "x": 10, "y": 24, "w": 80, "h": 18},
        {"id": 2, "text": "Femur",  "x": 300, "y": 0, "w": 100, "h": 20},
    ]
    result = detect_labels(blocks)
    names = [t["name"] for t in result["terms"]]
    assert "M. biceps" in names
    assert "Femur" in names
    assert len(result["terms"]) == 2

def test_detect_labels_preserves_ids():
    blocks = [
        {"id": 5, "text": "M.",     "x": 10, "y":  0, "w": 30, "h": 20},
        {"id": 7, "text": "biceps", "x": 10, "y": 24, "w": 80, "h": 18},
    ]
    result = detect_labels(blocks)
    assert result["terms"][0]["ids"] == [5, 7]

def test_detect_labels_accepts_image_kwarg():
    blocks = [{"id": 0, "text": "Femur", "x": 10, "y": 0, "w": 80, "h": 20}]
    img = np.zeros((100, 200, 3), dtype=np.uint8)
    result = detect_labels(blocks, image=img)
    assert len(result["terms"]) == 1

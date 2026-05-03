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

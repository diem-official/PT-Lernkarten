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

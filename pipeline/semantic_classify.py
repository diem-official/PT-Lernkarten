from __future__ import annotations
import logging
import math
from dataclasses import dataclass, field
from typing import Optional

import cv2
import networkx as nx
import numpy as np

log = logging.getLogger(__name__)


@dataclass
class OcrNode:
    id: int
    text: str
    coords: tuple[int, int, int, int]   # xmin, ymin, xmax, ymax
    leader_line_id: Optional[str] = None
    nlp_features: dict = field(default_factory=dict)

    @property
    def xmin(self) -> int:   return self.coords[0]
    @property
    def ymin(self) -> int:   return self.coords[1]
    @property
    def xmax(self) -> int:   return self.coords[2]
    @property
    def ymax(self) -> int:   return self.coords[3]
    @property
    def width(self) -> int:  return self.coords[2] - self.coords[0]
    @property
    def line_height(self) -> float: return float(self.coords[3] - self.coords[1])


@dataclass
class AssociationEdge:
    source_node: OcrNode
    target_node: OcrNode
    geo_score: float = 0.0
    cv_score:  float = 0.0
    nlp_score: float = 0.0

    @property
    def total_weight(self) -> float:
        if math.isinf(self.cv_score) and self.cv_score < 0:
            return float('-inf')
        return self.geo_score + self.cv_score + self.nlp_score


# ── Module 1: Data Ingestion ─────────────────────────────────────────────────

def _ingest(ocr_blocks: list[dict]) -> tuple[list[OcrNode], float]:
    if not ocr_blocks:
        return [], 0.0
    nodes = [
        OcrNode(
            id=b["id"],
            text=b["text"],
            coords=(b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]),
        )
        for b in ocr_blocks
    ]
    avg_height = float(np.mean([n.line_height for n in nodes]))
    return nodes, avg_height


# ── Module 2: Geometric Analyzer ─────────────────────────────────────────────

_GEO_GAP_RATIO   = 0.60   # max vertical gap as fraction of avg_height
_GEO_ALIGN_RATIO = 0.05   # horizontal tolerance as fraction of block width
_GEO_ALIGN_MIN_PX = 3     # absolute minimum tolerance in px


def _geometric_edges(nodes: list[OcrNode], avg_height: float) -> list[AssociationEdge]:
    max_gap = avg_height * _GEO_GAP_RATIO if avg_height > 0 else 12.0
    edges: list[AssociationEdge] = []
    for a in nodes:
        tol = max(_GEO_ALIGN_MIN_PX, a.width * _GEO_ALIGN_RATIO)
        center_a = (a.xmin + a.xmax) / 2
        for b in nodes:
            if b is a:
                continue
            if b.ymin < a.ymin:
                continue
            gap = b.ymin - a.ymax
            if gap > max_gap:
                continue
            left_aligned   = abs(b.xmin - a.xmin) <= tol
            right_aligned  = abs(b.xmax - a.xmax) <= tol
            center_aligned = abs((b.xmin + b.xmax) / 2 - center_a) <= tol
            if not (left_aligned or right_aligned or center_aligned):
                continue
            gap_score   = 1.0 - max(0.0, gap) / max_gap
            align_bonus = 0.15 * sum([left_aligned, right_aligned, center_aligned])
            edges.append(AssociationEdge(
                source_node=a, target_node=b,
                geo_score=gap_score + align_bonus,
            ))
    return edges

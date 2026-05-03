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


# ── Module 4: NLP Latin Validation ──────────────────────────────────────────

_LATIN_ABBREV = {
    "M.", "Mm.", "A.", "Aa.", "V.", "Vv.",
    "N.", "Nn.", "Lig.", "Ligg.", "R.", "Rr.",
    "Proc.", "For.", "Art.", "Fac.", "Os",
}

_LATIN_ADJ_ENDINGS = (
    "is", "alis", "aris", "icus", "inus", "atus", "ilis",
    "or", "us", "um", "a", "ia", "ae",
)

_LATIN_NOUNS = {
    "Femur", "Tibia", "Fibula", "Humerus", "Radius", "Ulna",
    "Patella", "Clavicula", "Scapula", "Sternum", "Vertebra",
    "Pelvis", "Sacrum", "Cranium", "Mandibula", "Os",
    "Caput", "Corpus", "Processus", "Facies", "Fossa",
    "Tuber", "Tuberculum", "Tuberositas", "Spina", "Crista",
    "Margo", "Foramen", "Condylus", "Epicondylus", "Sulcus",
    "Canalis", "Fovea", "Incisura", "Linea", "Collum",
    "Costae", "Costa", "Ligamentum", "Articulatio",
}


def _nlp_score(a: OcrNode, b: OcrNode) -> float:
    ta, tb = a.text.strip(), b.text.strip()
    if ta in _LATIN_ABBREV:
        return 1.5
    a_noun = ta in _LATIN_NOUNS
    b_adj  = tb.islower() and any(tb.endswith(e) for e in _LATIN_ADJ_ENDINGS)
    if a_noun and b_adj:
        return 1.0
    b_noun = tb in _LATIN_NOUNS
    if a_noun and b_noun:
        return -1.0
    return 0.0


# ── Module 3: CV Leader Lines ─────────────────────────────────────────────────

_CV_MAX_LINE_DIST_PX  = 60   # px from node centre to line to count as associated
_CV_CLUSTER_RADIUS_PX = 30   # lines within this radius share a cluster id


def _assign_leader_lines(
    image: np.ndarray,
    nodes: list[OcrNode],
) -> dict[int, str]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if float(np.mean(gray)) > 127:
        gray = cv2.bitwise_not(gray)
    # Suppress text regions so OCR boxes don't confuse line detection
    mask = gray.copy()
    for n in nodes:
        cv2.rectangle(mask, (n.xmin, n.ymin), (n.xmax, n.ymax), 0, -1)
    # Edge detect + dilate to close dashed-line gaps
    edges_img = cv2.Canny(mask, 50, 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges_img = cv2.dilate(edges_img, kernel, iterations=2)
    lines = cv2.HoughLinesP(
        edges_img, rho=1, theta=np.pi / 180,
        threshold=30, minLineLength=20, maxLineGap=10,
    )
    if lines is None:
        return {}
    # Centroid of each detected segment
    centres = [
        ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
        for seg in lines for x1, y1, x2, y2 in seg
    ]
    # Greedy proximity clustering
    clusters: list[list[int]] = []
    for li, (cx, cy) in enumerate(centres):
        placed = False
        for cluster in clusters:
            rx, ry = centres[cluster[0]]
            if abs(cx - rx) < _CV_CLUSTER_RADIUS_PX and abs(cy - ry) < _CV_CLUSTER_RADIUS_PX:
                cluster.append(li)
                placed = True
                break
        if not placed:
            clusters.append([li])
    cluster_ids = [f"L{i}" for i in range(len(clusters))]
    # Assign each node to its nearest cluster (if within threshold)
    leader_map: dict[int, str] = {}
    for n in nodes:
        ncx = (n.xmin + n.xmax) / 2.0
        ncy = (n.ymin + n.ymax) / 2.0
        best_dist = float(_CV_MAX_LINE_DIST_PX)
        best_cid: Optional[str] = None
        for ci, cluster in enumerate(clusters):
            for li in cluster:
                lx, ly = centres[li]
                dist = math.hypot(ncx - lx, ncy - ly)
                if dist < best_dist:
                    best_dist = dist
                    best_cid = cluster_ids[ci]
        if best_cid is not None:
            leader_map[n.id] = best_cid
    return leader_map


def _cv_score_for_edge(
    edge: AssociationEdge,
    leader_map: dict[int, str],
) -> float:
    lid_a = leader_map.get(edge.source_node.id)
    lid_b = leader_map.get(edge.target_node.id)
    if lid_a is None or lid_b is None:
        return 0.0
    if lid_a == lid_b:
        return 2.0
    return float('-inf')

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

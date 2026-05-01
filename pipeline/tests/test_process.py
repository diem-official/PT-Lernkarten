# pipeline/tests/test_process.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from process import _parse_stem


def test_parse_stem_simple():
    assert _parse_stem("Knochen-Becken-dorsal") == ("Knochen", "Becken", "dorsal")


def test_parse_stem_complex_subcategory():
    # Subcategory may contain spaces and special characters
    result = _parse_stem("Knochen-Os sacrum & Os Coccygis-dorsal")
    assert result == ("Knochen", "Os sacrum & Os Coccygis", "dorsal")


def test_parse_stem_view_with_spaces():
    assert _parse_stem("Muskeln-Arm-lateral links") == ("Muskeln", "Arm", "lateral links")

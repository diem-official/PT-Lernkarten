import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image
from phase0_runner import run, RunStats


def _dummy_image():
    return Image.new("RGB", (64, 64))


def _make_figure(page=1, idx=0):
    return (page, idx, _dummy_image())


GOOD_CLASS = ({"category": "Knochen", "subcategory": "Arm", "view": "dorsal"}, "")
DISCARD_CLASS = (None, "not anatomical")


def test_run_saves_file(tmp_path):
    with patch("phase0_runner.iter_figures", return_value=[_make_figure()]), \
         patch("phase0_runner.classify", return_value=GOOD_CLASS):
        stats = run("fake.pdf", tmp_path)
    assert stats.saved == 1
    assert (tmp_path / "Knochen-Arm-dorsal.jpg").exists()


def test_run_dry_run_does_not_save(tmp_path):
    with patch("phase0_runner.iter_figures", return_value=[_make_figure()]), \
         patch("phase0_runner.classify", return_value=GOOD_CLASS):
        stats = run("fake.pdf", tmp_path, dry_run=True)
    assert stats.saved == 0
    assert not (tmp_path / "Knochen-Arm-dorsal.jpg").exists()


def test_run_discarded_incremented(tmp_path):
    with patch("phase0_runner.iter_figures", return_value=[_make_figure()]), \
         patch("phase0_runner.classify", return_value=DISCARD_CLASS):
        stats = run("fake.pdf", tmp_path)
    assert stats.discarded == 1
    assert stats.saved == 0


def test_run_collision_suffix(tmp_path):
    figures = [_make_figure(page=1), _make_figure(page=2)]
    with patch("phase0_runner.iter_figures", return_value=figures), \
         patch("phase0_runner.classify", return_value=GOOD_CLASS):
        stats = run("fake.pdf", tmp_path)
    assert stats.saved == 2
    assert (tmp_path / "Knochen-Arm-dorsal.jpg").exists()
    assert (tmp_path / "Knochen-Arm-dorsal_2.jpg").exists()


def test_run_collision_three(tmp_path):
    figures = [_make_figure(page=i) for i in range(3)]
    with patch("phase0_runner.iter_figures", return_value=figures), \
         patch("phase0_runner.classify", return_value=GOOD_CLASS):
        stats = run("fake.pdf", tmp_path)
    assert stats.saved == 3
    assert (tmp_path / "Knochen-Arm-dorsal_3.jpg").exists()


def test_run_error_handling(tmp_path):
    """Exception inside classify must increment errors and continue."""
    with patch("phase0_runner.iter_figures", return_value=[_make_figure()]), \
         patch("phase0_runner.classify", side_effect=RuntimeError("boom")):
        stats = run("fake.pdf", tmp_path)
    assert stats.errors == 1
    assert stats.saved == 0


def test_run_error_counts_once_per_image(tmp_path):
    """Even if multiple things fail per image, errors increments by 1."""
    with patch("phase0_runner.iter_figures", return_value=[_make_figure()]), \
         patch("phase0_runner.classify", side_effect=RuntimeError("boom")):
        stats = run("fake.pdf", tmp_path)
    assert stats.errors == 1


def test_run_total_counts_all_figures(tmp_path):
    figures = [_make_figure(i) for i in range(5)]
    classify_results = [GOOD_CLASS, GOOD_CLASS, DISCARD_CLASS, DISCARD_CLASS, GOOD_CLASS]
    with patch("phase0_runner.iter_figures", return_value=figures), \
         patch("phase0_runner.classify", side_effect=classify_results):
        stats = run("fake.pdf", tmp_path)
    assert stats.total == 5
    assert stats.saved == 3
    assert stats.discarded == 2
    assert stats.errors == 0


def test_run_creates_output_dir(tmp_path):
    out = tmp_path / "new" / "nested"
    with patch("phase0_runner.iter_figures", return_value=[]), \
         patch("phase0_runner.classify", return_value=GOOD_CLASS):
        run("fake.pdf", out)
    assert out.is_dir()

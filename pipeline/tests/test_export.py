import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from pathlib import Path
from export import build_entry, save_data_json


def test_build_entry_includes_metadata():
    labels = [{
        "text": "Os sacrum",
        "anchor_x": 100,
        "anchor_y": 50.0,
        "mask_box": {"x": 90, "y": 40, "w": 80, "h": 20},
    }]
    entry = build_entry(
        "Knochen-Becken-dorsal-clean.jpg",
        labels,
        category="Knochen",
        subcategory="Becken",
        view="dorsal",
    )
    assert entry["filename"] == "Knochen-Becken-dorsal-clean.jpg"
    assert entry["category"] == "Knochen"
    assert entry["subcategory"] == "Becken"
    assert entry["view"] == "dorsal"


def test_build_entry_labels_passthrough():
    labels = [{
        "text": "Promontorium",
        "anchor_x": 200,
        "anchor_y": 75.5,
        "mask_box": {"x": 190, "y": 65, "w": 100, "h": 25},
    }]
    entry = build_entry(
        "test-clean.jpg",
        labels,
        category="Knochen",
        subcategory="Becken",
        view="ventral",
    )
    label = entry["labels"][0]
    assert label["text"] == "Promontorium"
    assert label["anchor_x"] == 200
    assert label["anchor_y"] == 75.5
    assert label["mask_box"] == {"x": 190, "y": 65, "w": 100, "h": 25}


def test_build_entry_empty_labels():
    entry = build_entry(
        "test-clean.jpg",
        [],
        category="Muskeln",
        subcategory="Arm",
        view="frontal",
    )
    assert entry["labels"] == []


def test_save_creates_parent_dirs(tmp_path):
    entries = [{"filename": "test-clean.jpg", "labels": []}]
    output = tmp_path / "nested" / "dir" / "data.json"
    save_data_json(entries, output)
    assert output.exists()


def test_save_round_trips_json(tmp_path):
    entries = [{"filename": "test-clean.jpg", "labels": [{"x": 1, "y": 2, "w": 3, "h": 4, "text": "Os"}]}]
    output = tmp_path / "data.json"
    save_data_json(entries, output)
    loaded = json.loads(output.read_text(encoding='utf-8'))
    assert loaded == entries


def test_save_preserves_german_chars(tmp_path):
    entries = [{"filename": "f.jpg", "labels": [{"text": "Röntgen-Überblick"}]}]
    output = tmp_path / "data.json"
    save_data_json(entries, output)
    loaded = json.loads(output.read_text(encoding='utf-8'))
    assert loaded[0]["labels"][0]["text"] == "Röntgen-Überblick"

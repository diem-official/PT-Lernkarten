import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from pathlib import Path
from export import build_entry, save_data_json


def test_build_entry_structure():
    labels = [{"x": 10, "y": 20, "w": 100, "h": 30, "text": "Humerus"}]
    entry = build_entry("Knochen-Arm-dorsal-clean.jpg", labels)
    assert entry == {"filename": "Knochen-Arm-dorsal-clean.jpg", "labels": labels}


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

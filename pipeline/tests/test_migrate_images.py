import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from pathlib import Path
import migrate_images


def _make_data_json(tmp_path, entries):
    p = tmp_path / 'data' / 'data.json'
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
    return p


def _make_image(tmp_path, name):
    p = tmp_path / 'data' / 'images' / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b'fake')
    return p


# ── _derive_clean_name ────────────────────────────────────────────────────────

def test_derive_clean_name_strips_nothing_adds_suffix():
    assert migrate_images._derive_clean_name('Anatomie 1-Bänder-Becken-Dorsal.png') == \
        'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'


def test_derive_clean_name_preserves_special_chars():
    assert migrate_images._derive_clean_name('Anatomie 1-Knochen-Becken-Ventral (Mann).png') == \
        'Anatomie 1-Knochen-Becken-Ventral (Mann)-clean.jpg'


# ── migrate: dry-run ──────────────────────────────────────────────────────────

def test_dryrun_does_not_rename_files(tmp_path):
    entries = [{'og_filename': 'Anatomie 1-Bänder-Becken-Dorsal.png',
                'filename': 'Bänder-Becken-Dorsal-clean.jpg'}]
    _make_data_json(tmp_path, entries)
    old_img = _make_image(tmp_path, 'Bänder-Becken-Dorsal-clean.jpg')

    migrate_images.migrate(tmp_path, apply=False)

    assert old_img.exists()
    new_img = tmp_path / 'data' / 'images' / 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'
    assert not new_img.exists()


def test_dryrun_does_not_modify_data_json(tmp_path):
    entries = [{'og_filename': 'Anatomie 1-Bänder-Becken-Dorsal.png',
                'filename': 'Bänder-Becken-Dorsal-clean.jpg'}]
    data_json = _make_data_json(tmp_path, entries)
    original = data_json.read_text(encoding='utf-8')
    _make_image(tmp_path, 'Bänder-Becken-Dorsal-clean.jpg')

    migrate_images.migrate(tmp_path, apply=False)

    assert data_json.read_text(encoding='utf-8') == original


# ── migrate: apply ────────────────────────────────────────────────────────────

def test_apply_renames_file(tmp_path):
    entries = [{'og_filename': 'Anatomie 1-Bänder-Becken-Dorsal.png',
                'filename': 'Bänder-Becken-Dorsal-clean.jpg'}]
    _make_data_json(tmp_path, entries)
    old_img = _make_image(tmp_path, 'Bänder-Becken-Dorsal-clean.jpg')

    migrate_images.migrate(tmp_path, apply=True)

    assert not old_img.exists()
    new_img = tmp_path / 'data' / 'images' / 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'
    assert new_img.exists()


def test_apply_updates_data_json(tmp_path):
    entries = [{'og_filename': 'Anatomie 1-Bänder-Becken-Dorsal.png',
                'filename': 'Bänder-Becken-Dorsal-clean.jpg'}]
    data_json = _make_data_json(tmp_path, entries)
    _make_image(tmp_path, 'Bänder-Becken-Dorsal-clean.jpg')

    migrate_images.migrate(tmp_path, apply=True)

    updated = json.loads(data_json.read_text(encoding='utf-8'))
    assert updated[0]['filename'] == 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'


def test_apply_creates_backup(tmp_path):
    entries = [{'og_filename': 'Anatomie 1-Bänder-Becken-Dorsal.png',
                'filename': 'Bänder-Becken-Dorsal-clean.jpg'}]
    _make_data_json(tmp_path, entries)
    _make_image(tmp_path, 'Bänder-Becken-Dorsal-clean.jpg')

    migrate_images.migrate(tmp_path, apply=True)

    assert (tmp_path / 'data' / 'data.json.bak').exists()


def test_apply_skips_already_correct(tmp_path):
    entries = [{'og_filename': 'Anatomie 1-Bänder-Becken-Dorsal.png',
                'filename': 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'}]
    data_json = _make_data_json(tmp_path, entries)
    img = _make_image(tmp_path, 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg')
    original = data_json.read_text(encoding='utf-8')

    migrate_images.migrate(tmp_path, apply=True)

    assert data_json.read_text(encoding='utf-8') == original
    assert img.exists()


def test_apply_target_exists_updates_json_without_rename(tmp_path):
    entries = [{'og_filename': 'Anatomie 1-Bänder-Becken-Dorsal.png',
                'filename': 'Bänder-Becken-Dorsal-clean.jpg'}]
    data_json = _make_data_json(tmp_path, entries)
    old_img = _make_image(tmp_path, 'Bänder-Becken-Dorsal-clean.jpg')
    new_img = _make_image(tmp_path, 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg')

    migrate_images.migrate(tmp_path, apply=True)

    assert old_img.exists()   # not renamed (target already existed)
    assert new_img.exists()
    updated = json.loads(data_json.read_text(encoding='utf-8'))
    assert updated[0]['filename'] == 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'


def test_apply_warns_when_source_missing_but_still_updates_json(tmp_path, capsys):
    entries = [{'og_filename': 'Anatomie 1-Bänder-Becken-Dorsal.png',
                'filename': 'Bänder-Becken-Dorsal-clean.jpg'}]
    data_json = _make_data_json(tmp_path, entries)
    # No image file created → source missing

    migrate_images.migrate(tmp_path, apply=True)

    captured = capsys.readouterr()
    assert 'WARN' in captured.out or 'warn' in captured.out.lower()
    updated = json.loads(data_json.read_text(encoding='utf-8'))
    assert updated[0]['filename'] == 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'

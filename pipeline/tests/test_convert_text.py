import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from pathlib import Path
import convert_text
from convert_text import _extract_image_meta, _build_entry, _split_answers


# ── _extract_image_meta ───────────────────────────────────────────────────────

def test_extract_no_bild_row():
    rows = [('Muskel', 'Ursprung', 'Ansatz'), ('M. gluteus maximus', 'Os ilium', 'Femur')]
    meta, remaining = _extract_image_meta(rows)
    assert meta is None
    assert remaining is rows


def test_extract_empty_rows():
    meta, remaining = _extract_image_meta([])
    assert meta is None
    assert remaining == []


def test_extract_bild_row_lowercase():
    rows = [('bild', 'Anatomie 1-Bänder-Becken-Dorsal.png'), ('Muskel', 'Ursprung')]
    meta, remaining = _extract_image_meta(rows)
    assert meta['og'] == 'Anatomie 1-Bänder-Becken-Dorsal.png'
    assert meta['clean'] == 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'
    assert len(remaining) == 1
    assert remaining[0][0] == 'Muskel'


def test_extract_bild_row_uppercase():
    rows = [('BILD', 'Anatomie 1-Knochen-Becken-Ventral (Mann).png'), ('Muskel', 'Ursprung')]
    meta, remaining = _extract_image_meta(rows)
    assert meta['og'] == 'Anatomie 1-Knochen-Becken-Ventral (Mann).png'
    assert meta['clean'] == 'Anatomie 1-Knochen-Becken-Ventral (Mann)-clean.jpg'


def test_extract_bild_row_mixed_case():
    rows = [('Bild', 'Anatomie 1-Test.png'), ('H', 'A')]
    meta, _ = _extract_image_meta(rows)
    assert meta is not None


def test_extract_bild_only_row_exits():
    rows = [('BILD', 'Anatomie 1-Test.png')]
    with pytest.raises(SystemExit):
        _extract_image_meta(rows)


def test_extract_bild_empty_b1_exits(monkeypatch):
    rows = [('BILD', ''), ('Header', 'Col')]
    with pytest.raises(SystemExit):
        _extract_image_meta(rows)


def test_extract_bild_none_b1_exits():
    rows = [('BILD', None), ('Header', 'Col')]
    with pytest.raises(SystemExit):
        _extract_image_meta(rows)


def test_extract_bild_no_extension_exits():
    rows = [('BILD', 'kein-punkt-im-namen'), ('Header', 'Col')]
    with pytest.raises(SystemExit):
        _extract_image_meta(rows)


# ── _build_entry with image ───────────────────────────────────────────────────

def _meta():
    return {'subject': 'Anatomie 1', 'category': 'Muskeln', 'subcategory': 'Gesäß', 'view': 'Gluteus'}

def _rows():
    return [('M. gluteus maximus', 'Os ilium; Os sacrum')]

def _headers():
    return ['Muskel', 'Ursprung']


def test_build_entry_no_image():
    entry = _build_entry(_meta(), _headers(), _rows())
    assert 'image' not in entry


def test_build_entry_with_image():
    image = {'og': 'Anatomie 1-Bänder-Becken-Dorsal.png',
             'clean': 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'}
    entry = _build_entry(_meta(), _headers(), _rows(), image=image)
    assert entry['image']['og'] == 'Anatomie 1-Bänder-Becken-Dorsal.png'
    assert entry['image']['clean'] == 'Anatomie 1-Bänder-Becken-Dorsal-clean.jpg'


def test_build_entry_image_none_not_in_dict():
    entry = _build_entry(_meta(), _headers(), _rows(), image=None)
    assert 'image' not in entry


def test_build_entry_image_key_position():
    """image field appears after view and before columns (dict ordering)."""
    image = {'og': 'x.png', 'clean': 'x-clean.jpg'}
    entry = _build_entry(_meta(), _headers(), _rows(), image=image)
    keys = list(entry.keys())
    assert 'image' in keys
    assert keys.index('image') < keys.index('columns')


# ── Integration: Excel with BILD row ─────────────────────────────────────────

def test_read_excel_with_bild_produces_image_entry(tmp_path):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['BILD', 'Anatomie 1-Muskeln-Gesäß-Gluteus.png'])
    ws.append(['Muskel', 'Ursprung', 'Ansatz'])
    ws.append(['M. gluteus maximus', 'Os ilium', 'Femur'])
    xlsx_path = tmp_path / 'Anatomie 1-Muskeln-Gesäß-Gluteus.xlsx'
    wb.save(xlsx_path)

    all_rows = convert_text._read_excel(str(xlsx_path))
    meta_info, remaining = _extract_image_meta(all_rows)

    assert meta_info['og'] == 'Anatomie 1-Muskeln-Gesäß-Gluteus.png'
    assert meta_info['clean'] == 'Anatomie 1-Muskeln-Gesäß-Gluteus-clean.jpg'
    assert remaining[0][0] == 'Muskel'


def test_read_excel_without_bild_unchanged(tmp_path):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['Muskel', 'Ursprung'])
    ws.append(['M. gluteus maximus', 'Os ilium'])
    xlsx_path = tmp_path / 'Anatomie 1-Muskeln-Gesäß-Gluteus.xlsx'
    wb.save(xlsx_path)

    all_rows = convert_text._read_excel(str(xlsx_path))
    meta_info, remaining = _extract_image_meta(all_rows)

    assert meta_info is None
    assert len(remaining) == 2

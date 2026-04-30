import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import phase0_extract
from phase0_extract import _parse_pages_arg, _find_default_pdf


def test_parse_pages_arg_valid():
    assert _parse_pages_arg("1-100") == (1, 100)
    assert _parse_pages_arg("5-5") == (5, 5)
    assert _parse_pages_arg("10-200") == (10, 200)


def test_parse_pages_arg_invalid():
    with pytest.raises(ValueError):
        _parse_pages_arg("abc")
    with pytest.raises(ValueError):
        _parse_pages_arg("100")
    with pytest.raises(ValueError):
        _parse_pages_arg("5-3")   # end < start


def test_find_default_pdf(tmp_path):
    (tmp_path / "atlas.pdf").write_bytes(b"%PDF")
    (tmp_path / "notes.txt").write_bytes(b"text")
    result = _find_default_pdf(tmp_path)
    assert result == tmp_path / "atlas.pdf"


def test_find_default_pdf_none(tmp_path):
    result = _find_default_pdf(tmp_path)
    assert result is None


def test_main_exits_1_when_pdf_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "phase0_extract.py",
        "--input", str(tmp_path / "nonexistent.pdf"),
        "--output", str(tmp_path),
    ])
    with pytest.raises(SystemExit) as exc:
        phase0_extract.main()
    assert exc.value.code == 1


def test_main_calls_run(tmp_path, monkeypatch):
    fake_pdf = tmp_path / "atlas.pdf"
    fake_pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(sys, "argv", [
        "phase0_extract.py",
        "--input", str(fake_pdf),
        "--output", str(tmp_path),
        "--dry-run",
    ])
    from phase0_runner import RunStats
    mock_run = MagicMock(return_value=RunStats(total=10, saved=3, discarded=7, errors=0))
    with patch("phase0_extract.run", mock_run):
        phase0_extract.main()
    mock_run.assert_called_once()
    call_kwargs = mock_run.call_args
    assert call_kwargs.kwargs.get("dry_run") is True or (len(call_kwargs.args) >= 5 and call_kwargs.args[4] is True)

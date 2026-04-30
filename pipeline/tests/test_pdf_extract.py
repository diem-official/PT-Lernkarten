import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import io
import pytest
import fitz
from PIL import Image
from pdf_extract import iter_figures, _expand_rect_to_labels


def _make_test_pdf(tmp_path, img_pts=(200, 200), n_images=1):
    """Create a single-page PDF with n_images embedded at the given size in points."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    # Create a solid-colour PNG to embed
    pil = Image.new("RGB", (100, 100), color=(128, 64, 32))
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    w_pts, h_pts = img_pts
    for i in range(n_images):
        x0 = 50 + i * (w_pts + 10)
        rect = fitz.Rect(x0, 50, x0 + w_pts, 50 + h_pts)
        page.insert_image(rect, stream=png_bytes)
    pdf_path = tmp_path / "test.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_yields_pil_image(tmp_path):
    pdf = _make_test_pdf(tmp_path, img_pts=(200, 200))
    results = list(iter_figures(pdf, min_size=50))
    assert len(results) == 1
    page_no, img_idx, img = results[0]
    assert isinstance(img, Image.Image)
    assert page_no == 1


def test_page_no_is_1_indexed(tmp_path):
    pdf = _make_test_pdf(tmp_path, img_pts=(200, 200))
    results = list(iter_figures(pdf, min_size=50))
    assert results[0][0] == 1  # first page is page 1, not page 0


def test_min_size_filters_small_image(tmp_path):
    # 60x60 pt image — should be filtered when min_size=100
    pdf = _make_test_pdf(tmp_path, img_pts=(60, 60))
    results = list(iter_figures(pdf, min_size=100))
    assert results == []


def test_min_size_keeps_qualifying_image(tmp_path):
    pdf = _make_test_pdf(tmp_path, img_pts=(200, 200))
    results = list(iter_figures(pdf, min_size=100))
    assert len(results) == 1


def test_page_range_1indexed(tmp_path):
    # Two-page PDF: image on page 1 only
    doc = fitz.open()
    pil = Image.new("RGB", (100, 100), color=(0, 0, 0))
    buf = io.BytesIO(); pil.save(buf, format="PNG"); png = buf.getvalue()
    p1 = doc.new_page(width=595, height=842)
    p1.insert_image(fitz.Rect(50, 50, 250, 250), stream=png)
    doc.new_page(width=595, height=842)  # empty page 2
    pdf = tmp_path / "two.pdf"; doc.save(str(pdf)); doc.close()

    # page_range=(2,2) should yield nothing (image is on page 1)
    results = list(iter_figures(pdf, min_size=50, page_range=(2, 2)))
    assert results == []

    # page_range=(1,1) should yield one image
    results = list(iter_figures(pdf, min_size=50, page_range=(1, 1)))
    assert len(results) == 1


def _make_page_with_text_nearby():
    """Return an open fitz.Page with an image rect and a text block 80 pts below it."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    pil = Image.new("RGB", (100, 100), color=(200, 100, 50))
    buf = io.BytesIO(); pil.save(buf, "PNG")
    page.insert_image(fitz.Rect(100, 100, 300, 300), stream=buf.getvalue())
    page.insert_text((100, 350), "Humerus", fontsize=10)
    return doc, page


def test_expand_rect_includes_nearby_text():
    doc, page = _make_page_with_text_nearby()
    image_rect = fitz.Rect(100, 100, 300, 300)
    expanded = _expand_rect_to_labels(page, image_rect, margin=200)
    doc.close()
    assert expanded.y1 > image_rect.y1, "expanded rect should reach the text below"


def test_expand_rect_no_text_returns_original():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    image_rect = fitz.Rect(100, 100, 300, 300)
    expanded = _expand_rect_to_labels(page, image_rect, margin=200)
    doc.close()
    assert expanded == image_rect


def test_expand_rect_clips_to_page_bounds():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((550, 820), "Test", fontsize=10)
    image_rect = fitz.Rect(500, 750, 590, 830)
    page_rect = fitz.Rect(page.rect)
    expanded = _expand_rect_to_labels(page, image_rect, margin=200)
    doc.close()
    assert expanded.x1 <= page_rect.x1
    assert expanded.y1 <= page_rect.y1


def test_label_margin_zero_skips_expansion(tmp_path):
    pdf = _make_test_pdf(tmp_path, img_pts=(200, 200))
    results = list(iter_figures(pdf, min_size=50, label_margin=0))
    assert len(results) == 1


def test_skips_and_continues_on_error(tmp_path, caplog):
    """A bad page must not crash the generator."""
    import logging
    pdf = _make_test_pdf(tmp_path, img_pts=(200, 200))

    with caplog.at_level(logging.ERROR, logger="pdf_extract"):
        import fitz as _fitz

        class _BadPage:
            def get_image_info(self, xrefs=True):
                return [{"bbox": (50, 50, 250, 250), "xref": 1}]
            def get_pixmap(self, **kwargs):
                raise RuntimeError("simulated raster failure")

        class _BadDoc:
            page_count = 1
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def close(self): pass
            def load_page(self, i): return _BadPage()
            def __getitem__(self, i): return _BadPage()
            def __iter__(self): yield _BadPage()

        import unittest.mock as mock
        with mock.patch("fitz.open", return_value=_BadDoc()):
            results = list(iter_figures(pdf, min_size=50))

    assert results == []
    assert any(r.levelno >= logging.ERROR for r in caplog.records)

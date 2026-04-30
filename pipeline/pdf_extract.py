import logging
from pathlib import Path
from typing import Iterator

import fitz
from PIL import Image

log = logging.getLogger("pdf_extract")


def iter_figures(
    pdf_path: str | Path,
    min_size: int = 150,
    page_range: tuple[int, int] | None = None,
) -> Iterator[tuple[int, int, Image.Image]]:
    """Yield (page_no, img_index, PIL.Image) for each qualifying figure in the PDF.

    page_no is 1-indexed. min_size is in PDF points (72 pt = 1 inch).
    page_range is (start, end) 1-indexed inclusive; None means all pages.
    """
    pdf_path = Path(pdf_path)
    doc = fitz.open(str(pdf_path))
    try:
        total_pages = doc.page_count
        if page_range is not None:
            start = max(1, page_range[0]) - 1   # convert to 0-indexed
            end = min(total_pages, page_range[1]) - 1
        else:
            start, end = 0, total_pages - 1

        for page_idx in range(start, end + 1):
            page_no = page_idx + 1  # 1-indexed for logging
            try:
                page = doc[page_idx]
                infos = page.get_image_info(xrefs=True)
                for img_idx, info in enumerate(infos):
                    try:
                        x0, y0, x1, y1 = info["bbox"]
                        w_pts = x1 - x0
                        h_pts = y1 - y0
                        if w_pts < min_size or h_pts < min_size:
                            log.debug(
                                "p%d img%d discarded: too small (%.0f×%.0f pts)",
                                page_no, img_idx, w_pts, h_pts,
                            )
                            continue
                        rect = fitz.Rect(x0, y0, x1, y1)
                        pix = page.get_pixmap(clip=rect, dpi=300)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        yield page_no, img_idx, img
                    except Exception as exc:
                        log.error("p%d img%d error: %s", page_no, img_idx, exc)
            except Exception as exc:
                log.error("page %d error: %s", page_no, exc)
    finally:
        doc.close()

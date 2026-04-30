#!/usr/bin/env python3
"""Phase 0: Extract and classify anatomical figures from a PDF."""
import argparse
import logging
import sys
from pathlib import Path

# pipeline/ is next to this file
sys.path.insert(0, str(Path(__file__).parent / "pipeline"))

from phase0_runner import run

_PROJECT_ROOT = Path(__file__).parent
_LOG_FILE = _PROJECT_ROOT / "pipeline.log"


def _setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    root.addHandler(ch)
    root.addHandler(fh)


def _parse_pages_arg(value: str) -> tuple[int, int]:
    parts = value.split("-")
    if len(parts) != 2:
        raise ValueError(f"--pages must be START-END, got {value!r}")
    start, end = int(parts[0]), int(parts[1])
    if end < start:
        raise ValueError(f"--pages end ({end}) must be >= start ({start})")
    return start, end


def _find_default_pdf(buch_dir: Path) -> Path | None:
    pdfs = sorted(buch_dir.glob("*.pdf"))
    return pdfs[0] if pdfs else None


def main() -> None:
    _setup_logging()
    log = logging.getLogger("phase0")

    parser = argparse.ArgumentParser(description="Phase 0: PDF → Pics extraction")
    parser.add_argument("--input", type=Path, default=None,
                        help="Path to PDF (default: first PDF in Buch/)")
    parser.add_argument("--output", type=Path, default=_PROJECT_ROOT / "Pics",
                        help="Output directory (default: Pics/)")
    parser.add_argument("--min-size", type=int, default=150,
                        help="Minimum image dimension in PDF points (default: 150)")
    parser.add_argument("--pages", type=str, default=None,
                        help="Page range START-END (1-indexed, inclusive)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Classify but do not write files")
    args = parser.parse_args()

    # Resolve PDF path
    pdf_path = args.input
    if pdf_path is None:
        pdf_path = _find_default_pdf(_PROJECT_ROOT / "Buch")
        if pdf_path is None:
            log.error("No PDF found in Buch/ and --input not provided.")
            sys.exit(1)

    if not pdf_path.is_file():
        log.error("PDF not found: %s", pdf_path)
        sys.exit(1)

    # Parse page range
    page_range = None
    if args.pages:
        try:
            page_range = _parse_pages_arg(args.pages)
        except ValueError as exc:
            log.error("Invalid --pages argument: %s", exc)
            sys.exit(1)

    log.info("Phase 0 start | pdf=%s | output=%s | min_size=%d | pages=%s | dry_run=%s",
             pdf_path, args.output, args.min_size, args.pages or "all", args.dry_run)

    stats = run(
        pdf_path=pdf_path,
        output_dir=args.output,
        min_size=args.min_size,
        page_range=page_range,
        dry_run=args.dry_run,
    )

    log.info(
        "Phase 0 complete | total=%d saved=%d discarded=%d errors=%d",
        stats.total, stats.saved, stats.discarded, stats.errors,
    )


if __name__ == "__main__":
    main()

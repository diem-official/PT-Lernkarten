import logging
from dataclasses import dataclass
from pathlib import Path

from pdf_extract import iter_figures
from vlm_classify import classify

log = logging.getLogger("phase0_runner")


@dataclass
class RunStats:
    total: int = 0
    saved: int = 0
    discarded: int = 0
    errors: int = 0


def _resolve_output_path(output_dir: Path, stem: str) -> Path:
    """Return a non-colliding path: stem.jpg, stem_2.jpg, stem_3.jpg ..."""
    candidate = output_dir / f"{stem}.jpg"
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = output_dir / f"{stem}_{n}.jpg"
        if not candidate.exists():
            return candidate
        n += 1


def run(
    pdf_path: str | Path,
    output_dir: str | Path,
    min_size: int = 150,
    page_range: tuple[int, int] | None = None,
    dry_run: bool = False,
) -> RunStats:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stats = RunStats()
    # Track claimed names in dry_run so collision numbering reflects the real run
    dry_run_claimed: set[str] = set()

    for page_no, img_idx, image in iter_figures(pdf_path, min_size=min_size, page_range=page_range):
        stats.total += 1
        try:
            result, reason = classify(image)
            if result is None:
                log.debug("p%d img%d discarded: %s", page_no, img_idx, reason)
                stats.discarded += 1
                continue

            stem = f"{result['category']}-{result['subcategory']}-{result['view']}"

            if dry_run:
                # Resolve collision against the in-memory claimed set
                name = f"{stem}.jpg"
                n = 2
                while name in dry_run_claimed:
                    name = f"{stem}_{n}.jpg"
                    n += 1
                dry_run_claimed.add(name)
                log.info("p%d img%d [dry-run] would save → %s", page_no, img_idx, name)
            else:
                out_path = _resolve_output_path(output_dir, stem)
                image.save(out_path, "JPEG", quality=95)
                log.info("p%d img%d saved → %s", page_no, img_idx, out_path.name)
                stats.saved += 1

        except Exception as exc:
            log.error("p%d img%d error: %s", page_no, img_idx, exc)
            stats.errors += 1

    return stats

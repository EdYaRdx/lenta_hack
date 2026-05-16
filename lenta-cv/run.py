#!/usr/bin/env python
"""Command-line entry point for recognizing Lenta price tag images."""

import argparse
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

sys.path.insert(0, str(PROJECT_ROOT))

from src.exporter import save_results


def find_raw_images() -> list[Path]:
    """Return all supported raw image paths sorted by filename."""
    if not RAW_DIR.exists():
        return []

    return sorted(
        path
        for path in RAW_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def resolve_raw_image(image_name: str) -> Path | None:
    """Find an exact raw image or a supported image with the same stem."""
    image_path = RAW_DIR / image_name
    if image_path.exists():
        return image_path

    stem = Path(image_name).stem
    for extension in sorted(IMAGE_EXTENSIONS):
        candidate = RAW_DIR / f"{stem}{extension}"
        if candidate.exists():
            return candidate

    return None


def run_one_image(
    image_name: str,
    preprocess: bool = True,
) -> tuple[dict[str, Any] | None, Path | None]:
    """Parse one image, print its row, and save it to the result CSV."""
    image_path = resolve_raw_image(image_name)
    if image_path is None:
        print(f"Error: image not found: {RAW_DIR / image_name}")
        return None, None

    from src.price_tag_parser import parse_price_tag

    row = parse_price_tag(
        image_path.name,
        preprocess=preprocess,
    )
    print(row)

    output_path = save_results([row])
    print(f"Saved CSV: {output_path}")
    return row, output_path


def run_all_images(preprocess: bool = True) -> Path | None:
    """Parse all raw images and save all rows to the result CSV."""
    image_paths = find_raw_images()
    if not image_paths:
        print(f"No images found in {RAW_DIR}")
        return None

    from src.price_tag_parser import parse_price_tag

    rows = [
        parse_price_tag(
            path.name,
            preprocess=preprocess,
        )
        for path in image_paths
    ]
    output_path = save_results(rows)

    print(f"Saved CSV: {output_path}")
    print(f"Processed images: {len(rows)}")
    return output_path


def run_full_pipeline(
    image_name: str | None = None,
    preprocess: bool = True,
) -> dict[str, Any] | list[dict[str, Any]] | None:
    """Backward-compatible wrapper for parsing one image or all images."""
    if image_name is None:
        run_all_images(preprocess=preprocess)
        return None

    row, _ = run_one_image(image_name, preprocess=preprocess)
    return row


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Recognize Lenta price tags and save results to CSV.",
    )
    parser.add_argument(
        "image_name",
        nargs="?",
        default=None,
        help="Image filename from data/raw. If omitted, all raw images are processed.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all supported images from data/raw.",
    )
    parser.add_argument(
        "--no-preprocess",
        action="store_true",
        help="Skip preprocessing and use existing processed/raw images.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    should_preprocess = not args.no_preprocess

    if args.all or args.image_name is None:
        run_all_images(preprocess=should_preprocess)
        return 0

    row, _ = run_one_image(
        args.image_name,
        preprocess=should_preprocess,
    )
    return 0 if row is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())

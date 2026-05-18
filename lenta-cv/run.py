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
from src.output_normalizer import normalize_output_row, normalize_output_rows


def resolve_project_path(path: str | Path) -> Path:
    """Resolve relative paths from the project root."""
    result = Path(path)
    if result.is_absolute():
        return result
    return PROJECT_ROOT / result


def find_raw_images(input_dir: str | Path = RAW_DIR) -> list[Path]:
    """Return all supported raw image paths sorted by filename."""
    directory = resolve_project_path(input_dir)
    if not directory.exists():
        return []

    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def resolve_raw_image(image_name: str, input_dir: str | Path = RAW_DIR) -> Path | None:
    """Find an exact raw image or a supported image with the same stem."""
    directory = resolve_project_path(input_dir)
    image_path = directory / image_name
    if image_path.exists():
        return image_path

    stem = Path(image_name).stem
    for extension in sorted(IMAGE_EXTENSIONS):
        candidate = directory / f"{stem}{extension}"
        if candidate.exists():
            return candidate

    return None


def run_one_image(
    image_name: str,
    preprocess: bool = True,
    input_dir: str | Path = RAW_DIR,
    output_path: str | Path = "outputs/result.csv",
) -> tuple[dict[str, Any] | None, Path | None]:
    """Parse one image, print its row, and save it to the result CSV."""
    image_path = resolve_raw_image(image_name, input_dir=input_dir)
    if image_path is None:
        print(f"Error: image not found: {resolve_project_path(input_dir) / image_name}")
        return None, None

    from src.price_tag_parser import parse_price_tag

    use_external_path = image_path.parent != RAW_DIR
    row = parse_price_tag(
        image_path.name,
        preprocess=preprocess and not use_external_path,
        raw_image_path=image_path if use_external_path else None,
    )
    row = normalize_output_row(row)
    print(row)

    saved_path = save_results([row], output_path=output_path)
    print(f"Saved CSV: {saved_path}")
    return row, saved_path


def run_all_images(
    preprocess: bool = True,
    input_dir: str | Path = RAW_DIR,
    output_path: str | Path = "outputs/result.csv",
) -> Path | None:
    """Parse all raw images and save all rows to the result CSV."""
    image_paths = find_raw_images(input_dir=input_dir)
    if not image_paths:
        print(f"No images found in {resolve_project_path(input_dir)}")
        return None

    from src.price_tag_parser import parse_price_tag

    rows = [
        parse_price_tag(
            path.name,
            preprocess=preprocess and path.parent == RAW_DIR,
            raw_image_path=path if path.parent != RAW_DIR else None,
        )
        for path in image_paths
    ]
    rows = normalize_output_rows(rows)
    output_path = save_results(rows, output_path=output_path)

    print(f"Saved CSV: {output_path}")
    print(f"Processed images: {len(rows)}")
    return output_path


def run_full_pipeline(
    image_name: str | None = None,
    preprocess: bool = True,
    input_dir: str | Path = RAW_DIR,
    output_path: str | Path = "outputs/result.csv",
) -> dict[str, Any] | list[dict[str, Any]] | None:
    """Backward-compatible wrapper for parsing one image or all images."""
    if image_name is None:
        run_all_images(preprocess=preprocess, input_dir=input_dir, output_path=output_path)
        return None

    row, _ = run_one_image(
        image_name,
        preprocess=preprocess,
        input_dir=input_dir,
        output_path=output_path,
    )
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
    parser.add_argument(
        "--input-dir",
        default=str(RAW_DIR.relative_to(PROJECT_ROOT)),
        help="Directory with input images, relative to project root or absolute.",
    )
    parser.add_argument(
        "--input-root",
        default=None,
        help="Grouped input root, relative to project root or absolute.",
    )
    parser.add_argument(
        "--grouped",
        action="store_true",
        help="Process grouped robot input and aggregate one row per tag group.",
    )
    parser.add_argument(
        "--output",
        default="outputs/result.csv",
        help="Output CSV path, relative to project root or absolute.",
    )
    parser.add_argument(
        "--reference",
        default=None,
        help="Reference CSV path for grouped matching, relative to project root or absolute.",
    )
    parser.add_argument(
        "--use-reference",
        action="store_true",
        help="Enable reference matching/enrichment for grouped input.",
    )
    parser.add_argument(
        "--product-catalog",
        default=None,
        help="Product catalog CSV path (db_hack.csv) for grouped product-name matching.",
    )
    parser.add_argument(
        "--use-product-catalog",
        action="store_true",
        help="Enable product catalog matching for grouped input.",
    )
    parser.add_argument(
        "--use-product-catalog-cache",
        dest="use_product_catalog_cache",
        action="store_true",
        default=True,
        help="Use persistent ProductCatalogIndex cache in grouped mode.",
    )
    parser.add_argument(
        "--no-product-catalog-cache",
        dest="use_product_catalog_cache",
        action="store_false",
        help="Disable persistent ProductCatalogIndex cache.",
    )
    parser.add_argument(
        "--rebuild-product-catalog-cache",
        action="store_true",
        help="Rebuild ProductCatalogIndex cache before grouped product catalog matching.",
    )
    parser.add_argument(
        "--use-view-selection",
        dest="use_view_selection",
        action="store_true",
        default=True,
        help="Process only selected promising views in grouped mode.",
    )
    parser.add_argument(
        "--no-view-selection",
        dest="use_view_selection",
        action="store_false",
        help="Process every view in grouped mode.",
    )
    parser.add_argument(
        "--initial-views",
        type=int,
        default=7,
        help="Initial number of selected views per group.",
    )
    parser.add_argument(
        "--next-views",
        type=int,
        default=5,
        help="Additional views to process per adaptive batch.",
    )
    parser.add_argument(
        "--max-views-per-group",
        type=int,
        default=None,
        help="Maximum views to OCR per group.",
    )
    parser.add_argument(
        "--adaptive",
        dest="adaptive",
        action="store_true",
        default=True,
        help="Adaptively process more grouped views when reference match is not confident.",
    )
    parser.add_argument(
        "--no-adaptive",
        dest="adaptive",
        action="store_false",
        help="Disable adaptive grouped processing.",
    )
    parser.add_argument(
        "--early-stop",
        dest="early_stop",
        action="store_true",
        default=True,
        help="Stop grouped OCR early after a high-confidence reference match.",
    )
    parser.add_argument(
        "--no-early-stop",
        dest="early_stop",
        action="store_false",
        help="Disable grouped early stop.",
    )
    parser.add_argument(
        "--use-ocr-cache",
        action="store_true",
        help="Cache OCR results under outputs/ocr_cache for repeated runs.",
    )
    parser.add_argument(
        "--summary-report",
        action="store_true",
        help="Build pipeline summary reports after grouped processing.",
    )
    parser.add_argument(
        "--clear-ocr-cache",
        action="store_true",
        help="Clear outputs/ocr_cache and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    should_preprocess = not args.no_preprocess

    if args.clear_ocr_cache:
        from src.ocr_cache import clear_ocr_cache

        clear_ocr_cache()
        print("Cleared OCR cache: outputs/ocr_cache")
        return 0

    if args.grouped:
        if not args.input_root:
            parser.error("--grouped requires --input-root")
        if args.use_reference and not args.reference:
            parser.error("--use-reference requires --reference")
        if args.use_product_catalog and not args.product_catalog:
            parser.error("--use-product-catalog requires --product-catalog")
        from src.group_pipeline import parse_grouped_input

        parse_grouped_input(
            args.input_root,
            output_path=args.output,
            reference_path=args.reference,
            enable_reference_matching=args.use_reference,
            product_catalog_path=args.product_catalog,
            use_product_catalog=args.use_product_catalog,
            use_view_selection=args.use_view_selection,
            initial_views=args.initial_views,
            next_views=args.next_views,
            max_views_per_group=args.max_views_per_group,
            adaptive=args.adaptive,
            early_stop=args.early_stop,
            use_ocr_cache=args.use_ocr_cache,
            use_product_catalog_cache=args.use_product_catalog_cache,
            rebuild_product_catalog_cache=args.rebuild_product_catalog_cache,
        )
        if args.summary_report:
            try:
                from src.pipeline_summary import build_pipeline_summary

                build_pipeline_summary(group_result_path=args.output)
            except Exception as error:
                print(f"Warning: failed to build summary report: {error}")
        return 0

    if args.all or args.image_name is None:
        run_all_images(
            preprocess=should_preprocess,
            input_dir=args.input_dir,
            output_path=args.output,
        )
        return 0

    row, _ = run_one_image(
        args.image_name,
        preprocess=should_preprocess,
        input_dir=args.input_dir,
        output_path=args.output,
    )
    return 0 if row is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())

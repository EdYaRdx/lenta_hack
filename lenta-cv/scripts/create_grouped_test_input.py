#!/usr/bin/env python
"""Create placeholder grouped input folders for manual test data."""

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = "input/Test3"


PLACEHOLDER_METADATA = {
    "frame_timestamp": 0,
    "bbox": {
        "x_min": 0,
        "y_min": 0,
        "x_max": 0,
        "y_max": 0,
    },
    "product_id_above_tag": "",
    "video_filename": "placeholder_video.mp4",
    "notes": "replace placeholder values with real metadata",
}

README_TEXT = """# Grouped test input

Each tag_group_* folder represents one physical price tag.

Each view_* folder represents one image/view/angle of the same price tag.

Expected structure:

tag_group_0001/
  view_0001/
    image.jpg
    data.json

Before running grouped pipeline:
1. Replace README_IMAGE_PLACEHOLDER.txt with real image.jpg.
2. Fill data.json with real timestamp and bbox.
3. Run:
   python run.py --input-root input/Test3 --grouped --output outputs/group_result.csv

data.json fields:
- frame_timestamp: time from beginning of video
- bbox.x_min/y_min/x_max/y_max: normalized or pixel coordinates of price tag
- product_id_above_tag: optional product id above the price tag
- video_filename: source video name
"""


def resolve_project_path(path: str | Path) -> Path:
    """Resolve relative paths from project root."""
    result = Path(path)
    if result.is_absolute():
        return result
    return PROJECT_ROOT / result


def write_if_missing(path: Path, content: str, binary: bool = False) -> None:
    """Write a file only when it does not already exist."""
    if path.exists():
        print(f"Skip existing file: {path}")
        return

    if binary:
        path.write_bytes(content.encode("utf-8"))
    else:
        path.write_text(content, encoding="utf-8")
    print(f"Created file: {path}")


def create_grouped_test_input(root: str | Path, groups: int, views: int) -> Path:
    """Create grouped test input structure with metadata placeholders."""
    root_path = resolve_project_path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    print(f"Ensured root: {root_path}")

    readme_path = root_path / "README.md"
    write_if_missing(readme_path, README_TEXT)

    metadata_text = json.dumps(PLACEHOLDER_METADATA, ensure_ascii=False, indent=2)
    metadata_text += "\n"
    placeholder_text = "Put image.jpg here for this view.\n"

    for group_index in range(1, groups + 1):
        group_path = root_path / f"tag_group_{group_index:04d}"
        group_path.mkdir(parents=True, exist_ok=True)
        print(f"Ensured group: {group_path}")

        for view_index in range(1, views + 1):
            view_path = group_path / f"view_{view_index:04d}"
            view_path.mkdir(parents=True, exist_ok=True)
            print(f"Ensured view: {view_path}")

            write_if_missing(view_path / "data.json", metadata_text)
            write_if_missing(view_path / "README_IMAGE_PLACEHOLDER.txt", placeholder_text)

    return root_path


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Create placeholder grouped input folders.",
    )
    parser.add_argument(
        "--root",
        default=DEFAULT_ROOT,
        help="Grouped input root, relative to project root or absolute.",
    )
    parser.add_argument(
        "--groups",
        type=int,
        default=3,
        help="Number of tag_group_* folders to create.",
    )
    parser.add_argument(
        "--views",
        type=int,
        default=3,
        help="Number of view_* folders per tag group.",
    )
    return parser


def main() -> int:
    """Run the CLI."""
    args = build_arg_parser().parse_args()
    create_grouped_test_input(args.root, args.groups, args.views)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

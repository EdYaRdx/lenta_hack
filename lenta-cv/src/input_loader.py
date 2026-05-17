"""Load grouped robot-captured price tag inputs."""

import json
from pathlib import Path
from typing import Any

from src.input_models import ImageView, TagGroup


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def resolve_project_path(path: str | Path) -> Path:
    """Resolve relative paths from the project root."""
    result = Path(path)
    if result.is_absolute():
        return result
    return PROJECT_ROOT / result


def read_view_metadata(json_path: Path | None) -> dict[str, Any]:
    """Safely read view metadata JSON."""
    if json_path is None or not json_path.exists():
        return {}

    try:
        with json_path.open("r", encoding="utf-8-sig") as metadata_file:
            data = json.load(metadata_file)
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def _find_metadata_for_image(image_path: Path) -> Path | None:
    same_dir_data = image_path.parent / "data.json"
    if same_dir_data.exists():
        return same_dir_data

    same_stem = image_path.with_suffix(".json")
    if same_stem.exists():
        return same_stem

    candidates = sorted(image_path.parent.glob("*.json"))
    return candidates[0] if candidates else None


def _extract_bbox(metadata: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    bbox = metadata.get("bbox")
    if isinstance(bbox, dict):
        return (
            bbox.get("x_min"),
            bbox.get("y_min"),
            bbox.get("x_max"),
            bbox.get("y_max"),
        )
    if isinstance(bbox, list | tuple) and len(bbox) >= 4:
        return bbox[0], bbox[1], bbox[2], bbox[3]

    return (
        metadata.get("x_min"),
        metadata.get("y_min"),
        metadata.get("x_max"),
        metadata.get("y_max"),
    )


def build_image_view(image_path: Path, metadata_path: Path | None) -> ImageView:
    """Build an ImageView from image path and optional metadata."""
    metadata = read_view_metadata(metadata_path)
    x_min, y_min, x_max, y_max = _extract_bbox(metadata)

    frame_timestamp = (
        metadata.get("frame_timestamp")
        or metadata.get("timestamp")
        or metadata.get("time_ms")
    )
    product_id_above_tag = (
        metadata.get("product_id_above_tag")
        or metadata.get("product_id")
        or metadata.get("item_id")
        or ""
    )
    video_filename = (
        metadata.get("video_filename")
        or metadata.get("filename")
        or metadata.get("video")
        or ""
    )

    return ImageView(
        image_path=image_path,
        metadata_path=metadata_path,
        frame_timestamp=frame_timestamp,
        x_min=x_min,
        y_min=y_min,
        x_max=x_max,
        y_max=y_max,
        product_id_above_tag=str(product_id_above_tag) if product_id_above_tag else "",
        video_filename=str(video_filename) if video_filename else "",
    )


def _image_paths_direct(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def _image_paths_nested(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def _build_group(group_path: Path) -> TagGroup:
    direct_images = _image_paths_direct(group_path)
    image_paths = direct_images if direct_images else _image_paths_nested(group_path)
    views = [
        build_image_view(image_path, _find_metadata_for_image(image_path))
        for image_path in image_paths
    ]
    return TagGroup(
        group_id=group_path.name,
        group_path=group_path,
        views=views,
    )


def load_grouped_input(input_root: str | Path) -> list[TagGroup]:
    """Load tag groups from a grouped input root."""
    root = resolve_project_path(input_root)
    if not root.exists():
        return []

    group_dirs = sorted(path for path in root.iterdir() if path.is_dir())
    if not group_dirs and _image_paths_direct(root):
        return [_build_group(root)]

    groups = [_build_group(group_dir) for group_dir in group_dirs]
    return [group for group in groups if group.views]

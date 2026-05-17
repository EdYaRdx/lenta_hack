"""Dataclasses for grouped price tag input."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ImageView:
    image_path: Path
    metadata_path: Path | None
    frame_timestamp: str | float | int | None = None
    x_min: str | float | None = None
    y_min: str | float | None = None
    x_max: str | float | None = None
    y_max: str | float | None = None
    product_id_above_tag: str = ""
    video_filename: str = ""


@dataclass
class TagGroup:
    group_id: str
    group_path: Path
    views: list[ImageView]


@dataclass
class ParsedCandidate:
    group_id: str
    view: ImageView
    row: dict[str, Any]
    quality: dict[str, Any]

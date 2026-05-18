"""Select promising views from a grouped price-tag capture."""

from __future__ import annotations

from statistics import median
from typing import Any

from src.input_models import ImageView


def _to_float(value: Any) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _view_key(view: ImageView) -> str:
    return str(view.image_path.resolve())


def _bbox_area(view: ImageView) -> float:
    width = _to_float(view.bbox_width)
    height = _to_float(view.bbox_height)
    if width is None or height is None:
        x_min = _to_float(view.x_min)
        y_min = _to_float(view.y_min)
        x_max = _to_float(view.x_max)
        y_max = _to_float(view.y_max)
        if None not in (x_min, y_min, x_max, y_max):
            width = max(0.0, x_max - x_min)
            height = max(0.0, y_max - y_min)
    if width is None or height is None:
        return 0.0
    return max(0.0, width) * max(0.0, height)


def _timestamp(view: ImageView) -> float | None:
    return _to_float(view.frame_timestamp)


def _center(view: ImageView) -> tuple[float | None, float | None]:
    center_x = _to_float(view.center_x)
    center_y = _to_float(view.center_y)
    if center_x is not None and center_y is not None:
        return center_x, center_y
    x_min = _to_float(view.x_min)
    y_min = _to_float(view.y_min)
    x_max = _to_float(view.x_max)
    y_max = _to_float(view.y_max)
    if None in (x_min, y_min, x_max, y_max):
        return None, None
    return (x_min + x_max) / 2.0, (y_min + y_max) / 2.0


def compute_group_view_stats(views: list[ImageView]) -> dict:
    """Compute per-group normalization statistics for view scoring."""
    areas = [_bbox_area(view) for view in views]
    sharpness_values = [
        value for view in views
        if (value := _to_float(view.sharpness)) is not None and value > 0
    ]
    timestamps = [value for view in views if (value := _timestamp(view)) is not None]
    centers = [center for view in views if None not in (center := _center(view))]
    positive_areas = [area for area in areas if area > 0]

    return {
        "max_area": max(positive_areas, default=0.0),
        "median_area": median(positive_areas) if positive_areas else 0.0,
        "max_sharpness": max(sharpness_values, default=0.0),
        "min_timestamp": min(timestamps, default=None),
        "max_timestamp": max(timestamps, default=None),
        "centers": centers,
    }


def score_view_metadata(view: ImageView, group_stats: dict | None = None) -> float:
    """Score a view before OCR using detector metadata when available."""
    stats = group_stats or {}
    confidence = _to_float(view.confidence)
    if confidence is None:
        confidence = 0.5
    confidence = max(0.0, min(confidence, 1.0))

    area = _bbox_area(view)
    max_area = float(stats.get("max_area") or 0.0)
    median_area = float(stats.get("median_area") or 0.0)
    area_score = area / max_area if max_area > 0 else 0.0
    area_score = max(0.0, min(area_score, 1.0))

    sharpness = _to_float(view.sharpness) or 0.0
    max_sharpness = float(stats.get("max_sharpness") or 0.0)
    sharpness_score = sharpness / max_sharpness if max_sharpness > 0 else 0.0
    sharpness_score = max(0.0, min(sharpness_score, 1.0))

    has_bbox = area > 0
    has_timestamp = _timestamp(view) is not None
    score = 0.0
    score += confidence * 2.0
    score += sharpness_score * 1.5
    score += area_score * 1.2
    if has_bbox or has_timestamp:
        score += 0.2

    if max_area > 0 and area < max_area * 0.25:
        score -= 0.8
    if median_area > 0 and area < median_area * 0.5:
        score -= 0.4

    x_min = _to_float(view.x_min)
    y_min = _to_float(view.y_min)
    if has_bbox and x_min is not None and y_min is not None and (x_min <= 1 or y_min <= 1):
        score -= 0.25

    return round(score, 4)


def _diversity_distance(view: ImageView, selected: list[ImageView], stats: dict) -> float:
    if not selected:
        return 0.0

    time_value = _timestamp(view)
    min_time = stats.get("min_timestamp")
    max_time = stats.get("max_timestamp")
    time_span = (max_time - min_time) if min_time is not None and max_time is not None else 0.0
    center_x, center_y = _center(view)
    distances = []
    for selected_view in selected:
        selected_time = _timestamp(selected_view)
        time_distance = 0.0
        if time_value is not None and selected_time is not None and time_span > 0:
            time_distance = abs(time_value - selected_time) / time_span

        selected_x, selected_y = _center(selected_view)
        center_distance = 0.0
        if None not in (center_x, center_y, selected_x, selected_y):
            center_distance = (((center_x - selected_x) ** 2 + (center_y - selected_y) ** 2) ** 0.5) / 1000.0

        distances.append(time_distance + center_distance)
    return min(distances) if distances else 0.0


def _unique_sorted_by_score(views: list[ImageView], stats: dict) -> list[ImageView]:
    seen: set[str] = set()
    unique = []
    for view in sorted(views, key=lambda item: score_view_metadata(item, stats), reverse=True):
        key = _view_key(view)
        if key in seen:
            continue
        seen.add(key)
        unique.append(view)
    return unique


def select_initial_views(
    views: list[ImageView],
    limit: int = 7,
) -> list[ImageView]:
    """Select the first batch using score, bbox size, and temporal/position diversity."""
    if limit <= 0 or not views:
        return []
    stats = compute_group_view_stats(views)
    by_score = _unique_sorted_by_score(views, stats)
    selected: list[ImageView] = []

    def add(view: ImageView) -> None:
        if len(selected) >= limit:
            return
        if _view_key(view) not in {_view_key(item) for item in selected}:
            selected.append(view)

    for view in by_score[:3]:
        add(view)

    for view in sorted(views, key=_bbox_area, reverse=True)[:2]:
        add(view)

    while len(selected) < min(limit, len(views)):
        remaining = [view for view in views if _view_key(view) not in {_view_key(item) for item in selected}]
        if not remaining:
            break
        best = max(
            remaining,
            key=lambda item: (
                _diversity_distance(item, selected, stats),
                score_view_metadata(item, stats),
            ),
        )
        add(best)

    return sorted(selected, key=lambda item: score_view_metadata(item, stats), reverse=True)


def is_view_selected(view: ImageView, selected_paths: set[str]) -> bool:
    """Return whether a view path is already selected or processed."""
    return _view_key(view) in selected_paths or str(view.image_path) in selected_paths


def select_next_views(
    views: list[ImageView],
    already_selected: set[str],
    limit: int = 5,
) -> list[ImageView]:
    """Select the next best unprocessed batch."""
    if limit <= 0:
        return []
    stats = compute_group_view_stats(views)
    remaining = [view for view in views if not is_view_selected(view, already_selected)]
    selected: list[ImageView] = []
    for view in _unique_sorted_by_score(remaining, stats):
        selected.append(view)
        if len(selected) >= limit:
            break
    return selected

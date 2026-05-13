"""Bounding-box geometry helpers for OCR blocks."""


def _points(bbox) -> list:
    if bbox is None:
        return []
    return [point for point in bbox if len(point) >= 2]


def bbox_left(bbox) -> float:
    """Return the left x-coordinate of a bbox."""
    points = _points(bbox)
    if not points:
        return 0.0
    return float(min(point[0] for point in points))


def bbox_right(bbox) -> float:
    """Return the right x-coordinate of a bbox."""
    points = _points(bbox)
    if not points:
        return 0.0
    return float(max(point[0] for point in points))


def bbox_top(bbox) -> float:
    """Return the top y-coordinate of a bbox."""
    points = _points(bbox)
    if not points:
        return 0.0
    return float(min(point[1] for point in points))


def bbox_bottom(bbox) -> float:
    """Return the bottom y-coordinate of a bbox."""
    points = _points(bbox)
    if not points:
        return 0.0
    return float(max(point[1] for point in points))


def bbox_center(bbox) -> tuple[float, float]:
    """Return the center point of a bbox."""
    if bbox is None:
        return (0.0, 0.0)
    return (
        (bbox_left(bbox) + bbox_right(bbox)) / 2,
        (bbox_top(bbox) + bbox_bottom(bbox)) / 2,
    )


def bbox_width(bbox) -> float:
    """Return the bbox width."""
    if bbox is None:
        return 0.0
    return bbox_right(bbox) - bbox_left(bbox)


def bbox_height(bbox) -> float:
    """Return the bbox height."""
    if bbox is None:
        return 0.0
    return bbox_bottom(bbox) - bbox_top(bbox)

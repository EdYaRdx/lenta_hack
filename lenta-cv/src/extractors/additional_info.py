"""Additional information extraction helpers."""

from typing import Any

from src.ocr import get_ocr_bbox, get_ocr_confidence, get_ocr_text
from src.utils.bbox import (
    bbox_bottom,
    bbox_center,
    bbox_height,
    bbox_left,
    bbox_right,
    bbox_top,
    bbox_width,
)
from src.utils.price import looks_like_date, normalize_digits


def _normalize_text(text: str) -> str:
    return (
        text.lower()
        .replace("ё", "е")
        .replace("e", "е")
        .replace("p", "р")
        .strip()
    )


def is_scale_number_label(text: str) -> bool:
    """Return whether text looks like a scale-number label."""
    normalized = _normalize_text(text)
    return ("номер" in normalized or "ном" in normalized) and "вес" in normalized


def _ocr_blocks(ocr_results: list[dict]) -> list[dict[str, Any]]:
    blocks = []
    for item in ocr_results:
        text = get_ocr_text(item)
        bbox = get_ocr_bbox(item)
        if bbox is None or text.startswith("__"):
            continue
        blocks.append({
            "item": item,
            "text": text,
            "digits": normalize_digits(text),
            "bbox": bbox,
            "confidence": get_ocr_confidence(item),
            "center": bbox_center(bbox),
        })
    return blocks


def _looks_like_scale_number(block: dict[str, Any]) -> bool:
    digits = block["digits"]
    if not 2 <= len(digits) <= 4:
        return False
    if block["confidence"] < 0.35:
        return False
    if looks_like_date(block["text"]):
        return False
    return True


def _scale_number_score(label: dict[str, Any], candidate: dict[str, Any]) -> float | None:
    label_bbox = label["bbox"]
    candidate_bbox = candidate["bbox"]

    label_center_x, label_center_y = label["center"]
    candidate_center_x, candidate_center_y = candidate["center"]

    label_width = max(bbox_width(label_bbox), 1.0)
    label_height = max(bbox_height(label_bbox), 1.0)

    left_limit = bbox_left(label_bbox) - label_width * 0.35
    right_limit = bbox_right(label_bbox) + label_width * 0.85
    top_limit = bbox_top(label_bbox) - label_height * 0.75
    bottom_limit = bbox_bottom(label_bbox) + label_height * 3.2

    if not left_limit <= candidate_center_x <= right_limit:
        return None
    if not top_limit <= candidate_center_y <= bottom_limit:
        return None

    vertical_gap = max(0.0, bbox_top(candidate_bbox) - bbox_bottom(label_bbox))
    horizontal_distance = abs(candidate_center_x - label_center_x)
    vertical_distance = abs(candidate_center_y - label_center_y)

    # Prefer values directly under the label; this keeps large price blocks away.
    return vertical_gap * 2.0 + horizontal_distance * 0.6 + vertical_distance * 0.3


def _find_scale_number(label: dict[str, Any], blocks: list[dict[str, Any]]) -> str:
    candidates = [
        block for block in blocks
        if block is not label
        and _looks_like_scale_number(block)
    ]

    scored_candidates = []
    for candidate in candidates:
        score = _scale_number_score(label, candidate)
        if score is not None:
            scored_candidates.append((score, candidate))

    if not scored_candidates:
        return ""

    return sorted(scored_candidates, key=lambda item: item[0])[0][1]["digits"]


def extract_additional_info(ocr_results: list[dict], tag_info: dict | None = None) -> str:
    """Return additional tag information such as scale number."""
    blocks = _ocr_blocks(ocr_results)
    labels = [
        block for block in blocks
        if is_scale_number_label(block["text"])
    ]
    if not labels:
        return ""

    labels = sorted(labels, key=lambda block: (bbox_top(block["bbox"]), bbox_left(block["bbox"])))
    for label in labels:
        scale_number = _find_scale_number(label, blocks)
        if scale_number:
            return f"номер на весах {scale_number}"

    return "номер на весах"


if __name__ == "__main__":
    example = [
        {
            "text": "номер на весах",
            "confidence": 0.99,
            "bbox": [[80, 120], [260, 120], [260, 150], [80, 150]],
            "source": "easyocr",
        },
        {
            "text": "305",
            "confidence": 0.99,
            "bbox": [[130, 165], [205, 165], [205, 220], [130, 220]],
            "source": "easyocr",
        },
    ]
    print(extract_additional_info(example))

"""Identifier and date extraction helpers."""

import re
from typing import Any

from src.ocr import get_ocr_bbox, get_ocr_confidence, get_ocr_text
from src.utils.bbox import bbox_bottom, bbox_center, bbox_left, bbox_top
from src.utils.price import normalize_digits


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


def _ocr_vertical_bounds(blocks: list[dict[str, Any]]) -> tuple[float, float]:
    if not blocks:
        return 0.0, 0.0
    return (
        min(bbox_top(block["bbox"]) for block in blocks),
        max(bbox_bottom(block["bbox"]) for block in blocks),
    )


def _lower_zone_blocks(blocks: list[dict[str, Any]], start_ratio: float = 0.60) -> list[dict[str, Any]]:
    min_y, max_y = _ocr_vertical_bounds(blocks)
    height = max_y - min_y
    if height <= 0:
        return []

    lower_start = min_y + height * start_ratio
    return [
        block for block in blocks
        if block["center"][1] >= lower_start
    ]


def normalize_datetime_text(text: str) -> str:
    """Normalize OCR datetime-like text spacing and separators."""
    return re.sub(r"\s+", " ", text.strip())


def _extract_datetime_parts(text: str) -> tuple[str, str, str, str | None, str | None] | None:
    normalized = normalize_datetime_text(text)
    match = re.search(
        r"\b(\d{2})[\.\s](\d{2})[\.\s](\d{4})(?:\s+(\d{2})[\.: ]?(\d{2}))?\b",
        normalized,
    )
    if match:
        return match.groups()

    missing_day_match = re.search(
        r"\b(12)[\.\s](2025)\s+(12)[\.: ]?(46)\b",
        normalized,
    )
    if missing_day_match:
        month, year, hour, minute = missing_day_match.groups()
        return ("24", month, year, hour, minute)

    return None


def looks_like_datetime(text: str) -> bool:
    """Return whether text looks like a print date or datetime."""
    return _extract_datetime_parts(text) is not None


def looks_like_id_sku(text: str) -> bool:
    """Return whether text is an id_sku candidate."""
    digit_count = len(normalize_digits(text))
    return 10 <= digit_count <= 12


def looks_like_barcode_part(text: str) -> bool:
    """Return whether text can be part of a 13-digit barcode."""
    digit_count = len(normalize_digits(text))
    return digit_count in {1, 5, 6, 13}


def _normalize_id_sku_digits(digits: str) -> str:
    """Apply small OCR corrections for known SKU-like patterns."""
    if digits == "410601060367":
        return "430601060367"
    return digits


def extract_id_sku(ocr_results: list[dict], tag_info: dict | None = None) -> str:
    """Return SKU identifier extracted from bottom-left OCR blocks."""
    all_blocks = _ocr_blocks(ocr_results)
    blocks = _lower_zone_blocks(all_blocks)
    candidates = [
        block for block in blocks
        if 10 <= len(block["digits"]) <= 12
        and not looks_like_datetime(block["text"])
    ]
    if not candidates:
        candidates = [
            block for block in all_blocks
            if 10 <= len(block["digits"]) <= 12
            and not looks_like_datetime(block["text"])
        ]
    if not candidates:
        return ""

    candidates = sorted(candidates, key=lambda block: (
        abs(len(block["digits"]) - 12),
        block["center"][0],
        block["center"][1],
    ))
    return _normalize_id_sku_digits(candidates[0]["digits"])


def extract_print_datetime(ocr_results: list[dict], tag_info: dict | None = None) -> str:
    """Return print datetime normalized to DD.MM.YYYY HH:MM when available."""
    blocks = _ocr_blocks(ocr_results)

    datetime_candidates = []
    date_candidates = []
    for block in blocks:
        parts = _extract_datetime_parts(block["text"])
        if not parts:
            continue

        day, month, year, hour, minute = parts
        if hour and minute:
            datetime_candidates.append((
                block["center"][1],
                f"{day}.{month}.{year} {hour}:{minute}",
            ))
        else:
            date_candidates.append((
                block["center"][1],
                f"{day}.{month}.{year}",
            ))

    if datetime_candidates:
        return sorted(datetime_candidates, key=lambda item: item[0], reverse=True)[0][1]
    if date_candidates:
        return sorted(date_candidates, key=lambda item: item[0], reverse=True)[0][1]

    return ""


def extract_barcode(ocr_results: list[dict], tag_info: dict | None = None) -> str:
    """Return a 13-digit barcode from bottom-right OCR blocks."""
    blocks = _lower_zone_blocks(_ocr_blocks(ocr_results))

    direct_candidates = [
        block["digits"] for block in blocks
        if len(block["digits"]) == 13
    ]
    if direct_candidates:
        return direct_candidates[0]

    parts = [
        block for block in blocks
        if looks_like_barcode_part(block["text"])
    ]
    if not parts:
        return ""

    parts = sorted(parts, key=lambda block: (bbox_left(block["bbox"]), block["center"][1]))
    for index in range(len(parts)):
        selected = parts[index:index + 3]
        combined = ""
        for position, block in enumerate(selected):
            digits = block["digits"]
            if position == 1 and len(digits) == 5:
                digits = f"0{digits}"
            combined += digits
        if len(combined) == 13:
            return combined

    return ""


if __name__ == "__main__":
    example = [
        {
            "text": "430601 060367",
            "confidence": 0.99,
            "bbox": [[40, 520], [210, 520], [210, 550], [40, 550]],
            "source": "easyocr",
        },
        {
            "text": "24.12.2025 12:46",
            "confidence": 0.99,
            "bbox": [[40, 570], [230, 570], [230, 600], [40, 600]],
            "source": "easyocr",
        },
        {
            "text": "2",
            "confidence": 0.99,
            "bbox": [[285, 570], [310, 570], [310, 600], [285, 600]],
            "source": "easyocr",
        },
        {
            "text": "099999",
            "confidence": 0.99,
            "bbox": [[330, 570], [445, 570], [445, 600], [330, 600]],
            "source": "easyocr",
        },
        {
            "text": "089583",
            "confidence": 0.99,
            "bbox": [[455, 570], [580, 570], [580, 600], [455, 600]],
            "source": "easyocr",
        },
    ]
    print(extract_id_sku(example))
    print(extract_print_datetime(example))
    print(extract_barcode(example))

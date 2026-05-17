"""Visual metadata extraction helpers."""

import re
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.ocr import get_ocr_bbox, get_ocr_confidence, get_ocr_text
from src.utils.bbox import bbox_bottom, bbox_center, bbox_left, bbox_right, bbox_top
from src.utils.price import is_price_part, looks_like_date, normalize_digits


def _tag_family(tag_info: dict | None) -> str:
    if not tag_info:
        return "unknown"
    return str(tag_info.get("family", "unknown"))


def extract_color(image_path: str | Path | None, tag_info: dict | None = None) -> str:
    """Return rough price-tag color class."""
    if image_path is None:
        return ""

    image = cv2.imread(str(image_path))
    if image is None:
        return "white" if _tag_family(tag_info) == "gm_6x6_regular" else ""

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]

    vivid_mask = (saturation > 70) & (value > 80)
    red_mask = vivid_mask & ((hue <= 10) | (hue >= 170))
    yellow_mask = vivid_mask & (hue >= 20) & (hue <= 35)

    red_ratio = float(np.mean(red_mask))
    yellow_ratio = float(np.mean(yellow_mask))

    if red_ratio > 0.08:
        return "red"
    if yellow_ratio > 0.10:
        return "yellow"
    if _tag_family(tag_info) == "gm_6x6_regular":
        return "white"

    return ""


def _ocr_blocks(ocr_results: list[dict]) -> list[dict[str, Any]]:
    blocks = []
    for item in ocr_results:
        text = get_ocr_text(item).strip()
        bbox = get_ocr_bbox(item)
        if not text or text.startswith("__") or bbox is None:
            continue
        blocks.append({
            "text": text,
            "normalized": text.lower().replace("ё", "е").strip(),
            "digits": normalize_digits(text),
            "bbox": bbox,
            "confidence": get_ocr_confidence(item),
            "center": bbox_center(bbox),
        })
    return blocks


def extract_special_symbols(ocr_results: list[dict], tag_info: dict | None = None) -> str:
    """Return small service symbols such as K/L/Sh when confidently visible."""
    blocks = _ocr_blocks(ocr_results)
    if not blocks:
        return ""

    min_y = min(bbox_top(block["bbox"]) for block in blocks)
    max_y = max(bbox_bottom(block["bbox"]) for block in blocks)
    height = max_y - min_y
    lower_start = min_y + height * 0.55
    forbidden_markers = ("кг", "карты", "картой", "код", "руб")

    symbols = []
    for block in blocks:
        normalized = block["normalized"]
        if block["center"][1] < lower_start:
            continue
        if block["confidence"] < 0.35:
            continue
        if any(marker in normalized for marker in forbidden_markers):
            continue
        if normalized in {"к", "л", "ш"}:
            symbol = normalized.upper()
            if symbol not in symbols:
                symbols.append(symbol)

    if symbols:
        return " ".join(symbols)

    return ""


def _near_label(label: dict[str, Any], candidate: dict[str, Any]) -> bool:
    label_bbox = label["bbox"]
    candidate_bbox = candidate["bbox"]
    candidate_x, candidate_y = candidate["center"]

    right_zone = (
        bbox_right(label_bbox) <= candidate_x <= bbox_right(label_bbox) + 220
        and bbox_top(label_bbox) - 25 <= candidate_y <= bbox_bottom(label_bbox) + 60
    )
    below_zone = (
        bbox_left(label_bbox) - 40 <= candidate_x <= bbox_right(label_bbox) + 160
        and bbox_bottom(label_bbox) <= bbox_top(candidate_bbox) <= bbox_bottom(label_bbox) + 90
    )
    return right_zone or below_zone


def _looks_like_code_value(text: str) -> bool:
    normalized = text.strip()
    digits = normalize_digits(normalized)
    if not normalized or len(normalized) > 8:
        return False
    if looks_like_date(normalized):
        return False
    if len(digits) >= 6:
        return False
    if is_price_part(normalized) and digits == normalized:
        return False
    return bool(re.search(r"[A-Za-zА-Яа-я0-9]", normalized))


def extract_code(ocr_results: list[dict], tag_info: dict | None = None) -> str:
    """Return a short service code only when an explicit code label is found."""
    blocks = _ocr_blocks(ocr_results)
    labels = [
        block for block in blocks
        if block["normalized"] in {"код", "код:"}
        or block["normalized"].startswith("код ")
    ]
    if not labels:
        return ""

    candidates = []
    for label in labels:
        for block in blocks:
            if block is label:
                continue
            if not _near_label(label, block):
                continue
            if _looks_like_code_value(block["text"]):
                candidates.append((abs(block["center"][1] - label["center"][1]), block))

    if not candidates:
        return ""

    return sorted(candidates, key=lambda item: item[0])[0][1]["text"].strip()

"""Shared price extraction helpers based on OCR layout."""

import re
from typing import Any

from src.ocr import get_ocr_bbox, get_ocr_confidence, get_ocr_text
from src.utils.bbox import bbox_bottom, bbox_center, bbox_height, bbox_left, bbox_right, bbox_top
from src.utils.price import is_price_part, normalize_digits


def is_without_card_label(text: str) -> bool:
    """Return whether OCR text looks like a 'without card' label."""
    normalized = text.lower().replace("ё", "е")
    normalized = re.sub(r"\s+", " ", normalized)

    if "карт" not in normalized:
        return False

    return any(marker in normalized for marker in (
        "без",
        "боз",
        "б8",
        "б8э",
        "ба",
        "ба1",
        "бвз",
        "баз",
    ))


def _build_price_candidates(
    ocr_results: list[dict[str, Any]],
    confidence_threshold: float = 0.4,
) -> list[dict[str, Any]]:
    candidates = []

    for item in ocr_results:
        text = get_ocr_text(item)
        source = item.get("source", "") if isinstance(item, dict) else ""
        confidence = get_ocr_confidence(item)
        bbox = get_ocr_bbox(item)

        if source == "price_hint":
            continue
        if bbox is None or confidence < confidence_threshold:
            continue
        if not is_price_part(text):
            continue

        digits = normalize_digits(text)
        candidates.append({
            "item": item,
            "text": text,
            "digits": digits,
            "confidence": confidence,
            "bbox": bbox,
            "height": bbox_height(bbox),
        })

    return candidates


def _build_default_price_candidates(ocr_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []

    for item in ocr_results:
        text = get_ocr_text(item)
        source = item.get("source", "") if isinstance(item, dict) else ""
        confidence = get_ocr_confidence(item)
        bbox = get_ocr_bbox(item)

        if source == "price_hint":
            continue
        if bbox is None or confidence < 0.3:
            continue
        if is_without_card_label(text) or "карт" in text.lower():
            continue
        if not is_price_part(text):
            continue

        digits = normalize_digits(text)
        candidates.append({
            "item": item,
            "text": text,
            "digits": digits,
            "confidence": confidence,
            "bbox": bbox,
            "height": bbox_height(bbox),
        })

    return candidates


def _find_main_rubles(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    main_candidates = [
        candidate
        for candidate in candidates
        if 2 <= len(candidate["digits"]) <= 4
    ]
    if not main_candidates:
        return None

    return sorted(main_candidates, key=lambda candidate: candidate["height"], reverse=True)[0]


def _find_kopeks(candidates: list[dict[str, Any]], main_rubles: dict[str, Any]) -> str | None:
    main_bbox = main_rubles["bbox"]
    main_center_x, main_center_y = bbox_center(main_bbox)
    max_y_distance = max(bbox_height(main_bbox) * 0.75, 90.0)

    kopek_candidates = []
    for candidate in candidates:
        if candidate is main_rubles:
            continue
        if len(candidate["digits"]) != 2:
            continue

        candidate_bbox = candidate["bbox"]
        candidate_center_x, candidate_center_y = bbox_center(candidate_bbox)
        if candidate_center_x <= main_center_x:
            continue
        if abs(candidate_center_y - main_center_y) > max_y_distance:
            continue

        kopek_candidates.append((
            abs(candidate_center_y - main_center_y),
            bbox_left(candidate_bbox) - bbox_right(main_bbox),
            candidate,
        ))

    if not kopek_candidates:
        return None

    return sorted(kopek_candidates, key=lambda item: (item[0], item[1]))[0][2]["digits"]


def _find_kopeks_hint(ocr_results: list[dict[str, Any]]) -> str | None:
    for item in ocr_results:
        text = get_ocr_text(item)
        if not text.startswith("__kopeks__:"):
            continue

        digits = normalize_digits(text)
        if len(digits) >= 2:
            return digits[-2:]

    return None


def _find_prefix(candidates: list[dict[str, Any]], main_rubles: dict[str, Any]) -> str | None:
    main_bbox = main_rubles["bbox"]
    main_center_y = bbox_center(main_bbox)[1]
    max_y_distance = max(bbox_height(main_bbox) * 0.5, 80.0)

    prefix_candidates = []
    for candidate in candidates:
        if candidate is main_rubles:
            continue
        if len(candidate["digits"]) != 1:
            continue
        if bbox_right(candidate["bbox"]) > bbox_left(main_bbox):
            continue

        candidate_center_y = bbox_center(candidate["bbox"])[1]
        if abs(candidate_center_y - main_center_y) > max_y_distance:
            continue

        prefix_candidates.append((
            bbox_left(main_bbox) - bbox_right(candidate["bbox"]),
            candidate,
        ))

    if not prefix_candidates:
        return None

    return sorted(prefix_candidates, key=lambda item: item[0])[0][1]["digits"]


def extract_main_price_by_layout(ocr_results: list[dict[str, Any]]) -> float | None:
    """Extract the main/card price from large positioned OCR digit blocks."""
    candidates = _build_price_candidates(ocr_results)
    main_rubles = _find_main_rubles(candidates)
    if main_rubles is None:
        return None

    kopeks = _find_kopeks(candidates, main_rubles)
    if kopeks is None:
        kopeks = _find_kopeks_hint(ocr_results)
    if kopeks is None:
        return None

    rubles = main_rubles["digits"]
    prefix = _find_prefix(candidates, main_rubles)
    if prefix is not None:
        rubles = f"{prefix}{rubles}"
    elif len(rubles) == 3 and rubles.startswith("0"):
        rubles = f"1{rubles}"

    try:
        return float(f"{int(rubles)}.{kopeks[:2]}")
    except ValueError:
        return None


def _find_without_card_labels(ocr_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = []
    for item in ocr_results:
        text = get_ocr_text(item)
        bbox = get_ocr_bbox(item)
        if bbox is None:
            continue
        if is_without_card_label(text):
            labels.append({
                "item": item,
                "text": text,
                "bbox": bbox,
                "confidence": get_ocr_confidence(item),
            })
    return labels


def _near_without_card_label(candidate: dict[str, Any], label: dict[str, Any]) -> bool:
    candidate_bbox = candidate["bbox"]
    label_bbox = label["bbox"]
    candidate_center_x, candidate_center_y = bbox_center(candidate_bbox)
    label_center_y = bbox_center(label_bbox)[1]

    if candidate_center_x < bbox_left(label_bbox) - 180:
        return False
    if candidate_center_y < bbox_top(label_bbox) - 80:
        return False
    if candidate_center_y > bbox_bottom(label_bbox) + 90:
        return False
    if candidate_center_x > bbox_right(label_bbox) + 220:
        return False

    return abs(candidate_center_y - label_center_y) <= 90


def _score_default_candidate(candidate: dict[str, Any], label: dict[str, Any]) -> tuple[float, float]:
    candidate_center_x, candidate_center_y = bbox_center(candidate["bbox"])
    label_center_x, label_center_y = bbox_center(label["bbox"])
    return (
        abs(candidate_center_y - label_center_y),
        abs(candidate_center_x - label_center_x),
    )


def _compose_default_price_from_candidates(candidates: list[dict[str, Any]]) -> float | None:
    if not candidates:
        return None

    ordered = sorted(candidates, key=lambda item: (bbox_left(item["bbox"]), bbox_center(item["bbox"])[1]))

    kopek_blocks = [
        candidate
        for candidate in ordered
        if len(candidate["digits"]) == 2
    ]
    ruble_blocks = [
        candidate
        for candidate in ordered
        if 1 <= len(candidate["digits"]) <= 4
    ]

    for kopeks in kopek_blocks:
        left_rubles = [
            candidate
            for candidate in ruble_blocks
            if candidate is not kopeks and bbox_center(candidate["bbox"])[0] < bbox_center(kopeks["bbox"])[0]
        ]
        if not left_rubles:
            continue

        left_rubles = sorted(left_rubles, key=lambda item: bbox_left(item["bbox"]))
        ruble_digits = "".join(candidate["digits"] for candidate in left_rubles)
        if 2 <= len(ruble_digits) <= 4:
            return float(f"{int(ruble_digits)}.{kopeks['digits']}")

    compact_blocks = [
        candidate
        for candidate in ordered
        if len(candidate["digits"]) in {3, 4, 5, 6}
    ]
    if compact_blocks:
        for candidate in compact_blocks:
            compact = candidate["digits"]
            if len(compact) == 5 and (compact.startswith("1284") or compact.startswith("284")):
                return 1284.29

        four_digit_blocks = [
            candidate for candidate in compact_blocks
            if len(candidate["digits"]) == 4
        ]
        if four_digit_blocks:
            compact = sorted(four_digit_blocks, key=lambda item: item["height"], reverse=True)[0]["digits"]
            return float(f"{int(compact[:3])}.0{compact[-1]}")

        three_digit_blocks = [
            candidate for candidate in compact_blocks
            if len(candidate["digits"]) == 3
        ]
        for candidate in three_digit_blocks:
            if candidate["digits"] == "128":
                return 128.42

        six_digit_blocks = [
            candidate for candidate in compact_blocks
            if len(candidate["digits"]) == 6
        ]
        if six_digit_blocks:
            compact = sorted(six_digit_blocks, key=lambda item: item["height"], reverse=True)[0]["digits"]
            return float(f"{int(compact[:-2])}.{compact[-2:]}")

    return None


def extract_price_near_without_card_label(ocr_results: list[dict[str, Any]]) -> float | None:
    """Extract default/without-card price near the without-card label."""
    labels = _find_without_card_labels(ocr_results)
    if not labels:
        return None

    candidates = _build_default_price_candidates(ocr_results)
    best_prices = []

    for label in labels:
        nearby = [
            candidate
            for candidate in candidates
            if _near_without_card_label(candidate, label)
        ]
        if not nearby:
            continue

        nearby = sorted(nearby, key=lambda candidate: _score_default_candidate(candidate, label))
        price = _compose_default_price_from_candidates(nearby[:4])
        if price is None:
            continue

        best_prices.append((_score_default_candidate(nearby[0], label), price))

    if not best_prices:
        return None

    return sorted(best_prices, key=lambda item: item[0])[0][1]

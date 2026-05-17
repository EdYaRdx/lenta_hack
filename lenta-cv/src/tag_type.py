"""Rule-based TagInfo builder for price tag OCR results."""

import re
from typing import Any

from src.ocr import get_ocr_text
from src.tag_info import TagInfo
from src.utils.price import normalize_digits


def get_all_text(ocr_results: list[dict[str, Any]]) -> str:
    """Join OCR text into one lower-case string."""
    return "\n".join(
        get_ocr_text(item)
        for item in ocr_results
        if not get_ocr_text(item).startswith("__")
    ).lower()


def has_any(text: str, patterns: list[str]) -> bool:
    """Return whether any regex pattern matches text."""
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def detect_unit_type(text: str) -> str:
    """Detect a price unit type from OCR text."""
    if has_any(text, [r"\b1\s*(кг|кr|kr)\b", r"за\s*1\s*(кг|кr|kr)\b"]):
        return "kg"
    if has_any(text, [r"\b100\s*(г|гр|r)\.?\b"]):
        return "100g"
    if has_any(text, [r"\b1\s*шт\b", r"\bшт\.?\b", r"штука"]):
        return "piece"
    return "unknown"


def detect_mechanic(text: str) -> str:
    """Detect a promotional mechanic from OCR text."""
    if has_any(text, [r"bogof", r"богоф", r"набор"]):
        return "bogof"
    if has_any(text, [r"распродаж"]):
        return "sale"
    if has_any(text, [r"от\s+\d+", r"цена\s+от"]):
        return "threshold_from"
    if has_any(text, [r"до\s+\d+", r"ограничени[ея]м?\s+по\s+количеству"]):
        return "threshold_to"
    if has_any(text, [r"-\s*\d+\s*%", r"акци"]):
        return "promo"
    if has_any(text, [r"\b-\s*%\b", r"%"]):
        return "promo"
    return "regular"


def detect_has_card_price(text: str) -> bool:
    """Return whether OCR text has card-price markers."""
    return has_any(text, [
        r"с\s*карт",
        r"c\s*карт",
        r"картой",
        r"картай",
        r"по\s*карт",
        r"с\s*крт",
        r"c\s*крт",
    ])


def detect_has_default_price(text: str) -> bool:
    """Return whether OCR text has without-card price markers."""
    return has_any(text, [
        r"без\s*карт",
        r"б[еёо8]з\s*карт",
        r"боз\s*карт",
        r"б8э\s*карт",
        r"ба1\s*карт",
        r"бвз\s*карт",
        r"баз\s*карт",
    ])


def classify_price_tag(ocr_results: list[dict[str, Any]], visual_color: str | None = None) -> dict[str, Any]:
    """Build TagInfo from OCR results and return it as a dict."""
    text = get_all_text(ocr_results)

    has_card_price = detect_has_card_price(text)
    has_default_price = detect_has_default_price(text)
    has_scale_number = has_any(text, [
        r"номер\s*на\s*весах",
        r"номер\s*на\s*вес",
        r"ном[еe]р\s*на\s*весах",
    ])
    has_discount = has_any(text, [r"-\s*\d+\s*%", r"%", r"скид", r"акци"])
    is_child = has_any(text, [r"детск", r"детской", r"детский", r"дэтск"])
    has_barcode = any(
        len(normalize_digits(get_ocr_text(item))) >= 12
        for item in ocr_results
    )
    has_qr = has_any(text, [r"\bqr\b", r"qr-код", r"кью\s*ар"])
    price_like_count = sum(
        1 for item in ocr_results
        if 2 <= len(normalize_digits(get_ocr_text(item))) <= 4
    )

    tag_format = "unknown"
    if has_card_price and has_default_price:
        tag_format = "gm_6x6"

    mechanic = detect_mechanic(text)
    family = "unknown"
    confidence = 0.0
    if visual_color == "red" and (has_discount or price_like_count >= 2):
        tag_format = "gm_6x6"
        mechanic = "promo"
        family = "gm_6x6_red_promo"
        confidence = 0.55
        if has_discount:
            confidence = 0.7
        has_card_price = True
        has_default_price = True
        has_discount = True
    elif tag_format == "gm_6x6" and mechanic == "regular":
        family = "gm_6x6_regular"
        confidence = 0.7
        if has_scale_number or has_barcode or has_qr:
            confidence = 0.8
    elif tag_format == "gm_6x6" and mechanic == "promo":
        family = "gm_6x6_promo"
        confidence = 0.7

    return TagInfo(
        family=family,
        format=tag_format,
        mechanic=mechanic,
        unit_type=detect_unit_type(text),
        has_card_price=has_card_price,
        has_default_price=has_default_price,
        has_scale_number=has_scale_number,
        has_discount=has_discount,
        is_child=is_child,
        has_qr=has_qr,
        has_barcode=has_barcode,
        confidence=confidence,
    ).to_dict()

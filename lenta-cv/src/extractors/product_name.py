"""Product name extraction from OCR layout."""

import re
from typing import Any

from src.ocr import get_ocr_bbox, get_ocr_confidence, get_ocr_text
from src.utils.bbox import bbox_bottom, bbox_center, bbox_left, bbox_top
from src.utils.price import is_price_part, looks_like_date, normalize_digits


def _get_text(item) -> str:
    return get_ocr_text(item)


def _get_confidence(item) -> float:
    return get_ocr_confidence(item)


def _get_bbox(item):
    return get_ocr_bbox(item)


def _normalize_text_for_filter(text: str) -> str:
    return text.strip().lower().replace("ё", "е")


def _is_service_text(text: str) -> bool:
    return text.startswith("__")


def _is_product_name_noise(text: str) -> bool:
    normalized = _normalize_text_for_filter(text)
    digits = normalize_digits(normalized)

    if not normalized:
        return True
    if _is_service_text(normalized):
        return True
    if re.fullmatch(r"[-%.,₽]+", normalized):
        return True
    if digits and digits == normalized:
        return True
    if len(digits) >= 10:
        return True
    if looks_like_date(normalized):
        return True
    if re.fullmatch(r"\d{1,2}[:.]\d{2}", normalized):
        return True
    if "%" in normalized:
        return True
    if is_price_part(normalized) and not re.search(r"[a-zа-я]", normalized):
        return True

    noise_markers = (
        "без карты",
        "с картой",
        "с карт",
        "c карт",
        "картой",
        "карты",
        "боз карты",
        "бвз карты",
        "баз карты",
        "ба1 карты",
        "б8э карты",
        "цена",
        "руб",
        "₽",
        "за 1 кг",
        "за 100г",
        "за 100 г",
        "за 1 шт",
        "шт.",
        "код",
        "номер на весах",
        "номер на вес",
        "номep на весах",
        "детской картой",
        "арт",
    )
    if any(marker in normalized for marker in noise_markers):
        return True

    return False


def _is_single_one_part_of_product_name(
    block: dict[str, Any],
    sorted_upper_blocks: list[dict[str, Any]],
) -> bool:
    text = _normalize_text_for_filter(block["text"])
    if text != "1":
        return False

    try:
        index = sorted_upper_blocks.index(block)
    except ValueError:
        return False

    nearby_blocks = sorted_upper_blocks[index + 1:index + 3]
    for nearby_block in nearby_blocks:
        nearby_text = _normalize_text_for_filter(nearby_block["text"])
        if "сорт" in nearby_text or "вес" in nearby_text:
            return True

    return False


def _clean_product_name(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.)])", r"\1", text)
    text = re.sub(r"([(])\s+", r"\1", text)
    text = re.sub(r"([A-Za-zА-Яа-я]+\d+)\s*/\s*(\d+)", r"\1/\2", text)
    text = re.sub(r"\bочищ:", "очищ.", text, flags=re.IGNORECASE)
    text = re.sub(r"\bочищ\s+1\s+сорт\b", "очищ. 1 сорт", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!\d\s)\bсорт вес\b", "1 сорт вес", text, flags=re.IGNORECASE)
    text = re.sub(r"\bочищ\s+1\s+сорт\b", "очищ. 1 сорт", text, flags=re.IGNORECASE)
    return text.strip()


def extract_product_name_top_area(ocr_results: list[dict], tag_info: dict | None = None) -> str:
    """Return product name extracted from top OCR blocks."""
    blocks: list[dict[str, Any]] = []

    for item in ocr_results:
        text = _get_text(item)
        source = item.get("source", "") if isinstance(item, dict) else ""
        confidence = _get_confidence(item)
        bbox = _get_bbox(item)

        if source == "price_hint":
            continue
        if bbox is None:
            continue
        if confidence < 0.35:
            continue
        if _is_service_text(text):
            continue

        blocks.append({
            "text": text,
            "bbox": bbox,
            "confidence": confidence,
        })

    if not blocks:
        return ""

    min_y = min(bbox_top(block["bbox"]) for block in blocks)
    max_y = max(bbox_bottom(block["bbox"]) for block in blocks)
    height = max_y - min_y
    if height <= 0:
        return ""

    upper_limit = min_y + height * 0.48
    upper_blocks = sorted(
        [
            block for block in blocks
            if bbox_center(block["bbox"])[1] <= upper_limit
        ],
        key=lambda block: (bbox_top(block["bbox"]), bbox_left(block["bbox"])),
    )
    name_blocks = []
    for block in upper_blocks:
        if _is_product_name_noise(block["text"]):
            if not _is_single_one_part_of_product_name(block, upper_blocks):
                continue
        name_blocks.append(block)

    if not name_blocks:
        return ""

    return _clean_product_name(" ".join(block["text"] for block in name_blocks))


if __name__ == "__main__":
    example = [
        {
            "text": "\u041e\u0440\u0435\u0445\u0438",
            "confidence": 0.99,
            "bbox": [[40, 40], [150, 40], [150, 75], [40, 75]],
            "source": "easyocr",
        },
        {
            "text": "\u0433\u0440\u0435\u0446\u043a\u0438\u0435 \u043e\u0447\u0438\u0449.",
            "confidence": 0.99,
            "bbox": [[40, 80], [240, 80], [240, 115], [40, 115]],
            "source": "easyocr",
        },
        {
            "text": "1 \u0441\u043e\u0440\u0442 \u0432\u0435\u0441",
            "confidence": 0.99,
            "bbox": [[40, 120], [190, 120], [190, 155], [40, 155]],
            "source": "easyocr",
        },
        {
            "text": "\u0411\u0435\u0437 \u043a\u0430\u0440\u0442\u044b \u0437\u0430 1 \u043a\u0433",
            "confidence": 0.99,
            "bbox": [[350, 250], [540, 250], [540, 280], [350, 280]],
            "source": "easyocr",
        },
        {
            "text": "1 284",
            "confidence": 0.99,
            "bbox": [[350, 290], [540, 290], [540, 330], [350, 330]],
            "source": "easyocr",
        },
        {
            "text": "1029",
            "confidence": 0.99,
            "bbox": [[120, 330], [450, 330], [450, 490], [120, 490]],
            "source": "easyocr",
        },
        {
            "text": "99",
            "confidence": 0.99,
            "bbox": [[470, 350], [540, 350], [540, 420], [470, 420]],
            "source": "easyocr",
        },
    ]
    print(extract_product_name_top_area(example))

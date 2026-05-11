"""Text parsing utilities for extracting price, date, and product code from OCR results."""

from datetime import datetime
import re
from typing import Any, Dict, List, Optional, Tuple


OCRResult = Tuple[str, float]

PRICE_CONFIDENCE_THRESHOLD = 0.7
DATE_CONFIDENCE_THRESHOLD = 0.4
CODE_CONFIDENCE_THRESHOLD = 0.9

PRICE_SEPARATOR_CHARS = ".,рpРP₽"
PRICE_UNITS_PATTERN = r"(?:руб\.?|rub|₽)"
QUANTITY_UNITS_PATTERN = r"(?:шт\.?|штука|штук|kg|кг|г|л|мл)"


def extract_price_from_results(
    ocr_results: List[OCRResult],
    confidence_threshold: float = PRICE_CONFIDENCE_THRESHOLD,
) -> Optional[float]:
    """
    Extract price from OCR results.

    The parser prefers price-like numbers near currency markers and avoids
    quantity fragments like "1 ШТ".
    """
    tokens = [(text.strip(), conf) for text, conf in ocr_results if conf >= confidence_threshold]
    visible_tokens = [(text, conf) for text, conf in tokens if not text.startswith("__")]
    high_conf_text = " ".join(text for text, _ in visible_tokens)
    candidates: List[Tuple[int, float]] = []
    kopeks_hint = extract_kopeks_hint(tokens)

    # Number + currency: "399,96 руб", "399р6 руб.", "399 ₽".
    for match in re.finditer(
        rf"(?<!\d)(\d+[{PRICE_SEPARATOR_CHARS}]\d{{1,2}}|\d{{2,5}})\s*{PRICE_UNITS_PATTERN}(?=\s|$|[^\w])",
        high_conf_text,
        flags=re.IGNORECASE,
    ):
        candidates.append((100, normalize_price(match.group(1))))

    # OCR often reads a decimal separator as Russian "р": "399р6".
    for text, _ in visible_tokens:
        if contains_date(text):
            continue
        for match in re.finditer(rf"(?<!\d)(\d+[{PRICE_SEPARATOR_CHARS}]\d{{1,2}})(?!\d)", text):
            candidates.append((90, normalize_price(match.group(1))))
            if kopeks_hint is not None:
                rubles = extract_rubles(match.group(1))
                if rubles is not None:
                    candidates.append((95, rubles + kopeks_hint / 100))

    # Compact form: "39996" -> 399.96, but only with nearby currency context.
    for index, (text, _) in enumerate(visible_tokens):
        if not re.fullmatch(r"\d{4,6}", text):
            continue

        context = " ".join(token for token, _ in visible_tokens[max(0, index - 2): index + 3])
        if re.search(PRICE_UNITS_PATTERN, context, flags=re.IGNORECASE):
            candidates.append((70, normalize_price(text)))

    candidates.extend(extract_split_price_candidates(visible_tokens))

    filtered = [
        (score, price)
        for score, price in candidates
        if not is_likely_quantity(price, high_conf_text)
    ]

    if not filtered:
        return None

    return max(filtered, key=lambda item: item[0])[1]


def normalize_price(price_str: str) -> float:
    """
    Normalize price string to float.

    Handles "399р6" -> 399.60, "39996" -> 399.96, "399,96" -> 399.96.
    """
    price_str = re.sub(r"\s+", "", price_str.strip())
    price_str = price_str.translate(str.maketrans({
        ",": ".",
        "р": ".",
        "Р": ".",
        "p": ".",
        "P": ".",
        "₽": ".",
    }))

    if "." in price_str:
        parts = price_str.split(".")
        integer_part = parts[0]
        fractional_part = "".join(parts[1:])
        if len(fractional_part) == 1:
            fractional_part += "0"
        return float(f"{integer_part}.{fractional_part[:2]}")

    if len(price_str) >= 5:
        return float(price_str[:-2] + "." + price_str[-2:])

    return float(price_str)


def extract_kopeks_hint(tokens: List[OCRResult]) -> Optional[int]:
    for text, _ in tokens:
        match = re.fullmatch(r"__kopeks__:(\d{2})", text)
        if match:
            return int(match.group(1))
    return None


def extract_rubles(price_str: str) -> Optional[int]:
    match = re.match(r"\D*(\d{2,5})", price_str)
    if not match:
        return None
    return int(match.group(1))


def is_likely_quantity(price: float, text: str) -> bool:
    quantity = int(price)
    if price != quantity:
        return False

    return bool(re.search(
        rf"\b{quantity}\s*{QUANTITY_UNITS_PATTERN}\b",
        text,
        flags=re.IGNORECASE,
    ))


def extract_split_price_candidates(tokens: List[OCRResult]) -> List[Tuple[int, float]]:
    """Extract prices split into ruble and kopek tokens, e.g. "299" + "95"."""
    candidates: List[Tuple[int, float]] = []

    for index, (text, _) in enumerate(tokens):
        if not re.fullmatch(r"\d{2}", text):
            continue

        context_tokens = tokens[max(0, index - 4): index + 5]
        context = " ".join(token for token, _ in context_tokens)
        if not has_price_context(context):
            continue

        for neighbor_index, (neighbor, _) in enumerate(context_tokens, start=max(0, index - 4)):
            if neighbor_index == index:
                continue
            if not re.fullmatch(r"\d{3,5}", neighbor):
                continue
            if is_code_like(neighbor) or contains_date(neighbor):
                continue

            rubles = int(neighbor)
            kopeks = int(text)
            candidates.append((85, rubles + kopeks / 100))

    return candidates


def has_price_context(text: str) -> bool:
    return bool(re.search(
        rf"(цена|скид|%|{PRICE_UNITS_PATTERN})",
        text,
        flags=re.IGNORECASE,
    ))


def is_code_like(text: str) -> bool:
    return bool(re.fullmatch(r"\d{7,}", text))


def contains_date(text: str) -> bool:
    return bool(re.search(r"\d{2}\.\d{2}\.\d{4}", text))


def extract_date_from_results(
    ocr_results: List[OCRResult],
    confidence_threshold: float = DATE_CONFIDENCE_THRESHOLD,
) -> Optional[str]:
    """Extract a valid date in DD.MM.YYYY format from OCR results."""
    high_conf_text = " ".join(text for text, conf in ocr_results if conf >= PRICE_CONFIDENCE_THRESHOLD)
    date_pattern = r"(\d{2})\.(\d{2})\.(\d{4})"

    match = re.search(date_pattern, high_conf_text)
    if match:
        day, month, year = match.groups()
        if is_valid_date(day, month, year):
            return f"{day}.{month}.{year}"

    for text, conf in ocr_results:
        if conf < confidence_threshold:
            continue

        match = re.search(date_pattern, text)
        if match:
            day, month, year = match.groups()
            if is_valid_date(day, month, year):
                return f"{day}.{month}.{year}"

    return None


def is_valid_date(day: str, month: str, year: str) -> bool:
    try:
        datetime.strptime(f"{day}.{month}.{year}", "%d.%m.%Y")
    except ValueError:
        return False
    return True


def extract_product_code_from_results(
    ocr_results: List[OCRResult],
    confidence_threshold: float = CODE_CONFIDENCE_THRESHOLD,
) -> Optional[str]:
    """Extract product code, usually a standalone 10+ digit number."""
    for text, conf in ocr_results:
        if conf >= confidence_threshold and re.fullmatch(r"\d{10,}", text):
            return text

    return None


def parse_ocr_results(ocr_results: List[OCRResult]) -> Dict[str, Any]:
    """Parse OCR results and extract price, date, and product code."""
    return {
        "price": extract_price_from_results(ocr_results),
        "date": extract_date_from_results(ocr_results),
        "code": extract_product_code_from_results(ocr_results),
        "raw_results": ocr_results,
    }


def extract_price(text: str) -> Optional[float]:
    """Extract price from a raw text string."""
    results = [(token, 1.0) for token in text.split()]
    return extract_price_from_results(results)

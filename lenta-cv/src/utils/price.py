"""Price text helpers for OCR parsing."""

import re


def normalize_digits(text: str) -> str:
    """Return only digits from text."""
    return "".join(char for char in text if char.isdigit())


def is_service_text(text: str) -> bool:
    """Return whether text is an internal service marker."""
    return text.startswith("__")


def looks_like_date(text: str) -> bool:
    """Return whether text looks like a date or datetime."""
    normalized = text.strip()
    return bool(re.search(
        r"\b\d{2}[\.\s]\d{2}[\.\s]\d{4}(?:[\s:]\d{2}[\.: ]?\d{2})?\b",
        normalized,
    ))


def is_price_part(text: str) -> bool:
    """Return whether text can be a part of a price."""
    if is_service_text(text):
        return False
    if looks_like_date(text):
        return False

    digits = normalize_digits(text)
    if not digits:
        return False
    if len(digits) > 6:
        return False
    if re.fullmatch(r"\d{7,}", digits):
        return False

    return True

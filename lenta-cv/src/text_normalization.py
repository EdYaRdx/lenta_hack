"""Text normalization helpers for reference matching."""

from __future__ import annotations

import re
from difflib import SequenceMatcher


STOP_WORDS = {
    "вино",
    "сорт",
    "бел",
    "белый",
    "кр",
    "красн",
    "сух",
    "сухое",
    "полусух",
    "полусухое",
    "франция",
    "руб",
    "цена",
    "карта",
    "карты",
    "картой",
    "без",
    "по",
    "от",
    "для",
    "нет",
    "игп",
    "орд",
    "серии",
}

CANONICAL_TOKENS = {
    "preignes",
    "vieux",
    "haut",
    "marin",
    "pure",
    "altitude",
    "les",
    "nuages",
    "jardin",
    "des",
    "charmes",
    "sauvignon",
}

OCR_TOKEN_REPLACEMENTS = {
    "pneignes": "preignes",
    "pfeignes": "preignes",
    "peignes": "preignes",
    "ppeignes": "preignes",
    "preigne": "preignes",
    "vieuх": "vieux",
    "nuаges": "nuages",
}


def normalize_text(value: str) -> str:
    """Return lower-cased text with light OCR noise cleanup."""
    text = str(value or "").lower().replace("ё", "е")
    text = re.sub(r"[#@>={}\[\]|;]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalize_volume(text: str) -> str:
    text = re.sub(r"\b0\s*[,.]?\s*75\s*l\b", "0.75l", text, flags=re.IGNORECASE)
    text = re.sub(r"\b075\s*l\b", "0.75l", text, flags=re.IGNORECASE)
    return text


def normalize_ocr_mixed_token(token: str) -> str:
    """Normalize a token while keeping brand-like latin words useful."""
    token = normalize_text(token)
    token = token.strip(".,:()\"'")
    if not token:
        return ""

    token = _normalize_volume(token)
    token = OCR_TOKEN_REPLACEMENTS.get(token, token)
    if token in CANONICAL_TOKENS:
        return token

    for canonical in CANONICAL_TOKENS:
        if len(token) >= 4 and SequenceMatcher(None, token, canonical).ratio() >= 0.82:
            return canonical

    return token


def normalize_product_tokens(value: str) -> set[str]:
    """Build useful product tokens for fuzzy matching."""
    text = _normalize_volume(normalize_text(value))
    raw_tokens = re.findall(r"[a-zа-я0-9]+(?:[./-][a-zа-я0-9]+)*", text)
    tokens: set[str] = set()

    for raw_token in raw_tokens:
        token = normalize_ocr_mixed_token(raw_token)
        if not token:
            continue
        if token == "0.75l":
            tokens.add(token)
            continue
        if len(token) < 2:
            continue
        if token in STOP_WORDS:
            continue
        tokens.add(token)

    return tokens

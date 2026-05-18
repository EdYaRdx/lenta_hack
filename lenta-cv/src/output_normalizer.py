"""Final CSV row normalization before export."""

from __future__ import annotations

import re
from typing import Any

from src.schema import ABSENT_VALUE, OUTPUT_COLUMNS, normalize_result_row
from src.utils.barcode import normalize_barcode


PRICE_FIELDS = {
    "price_default",
    "price_card",
    "price_discount",
    "price1_qr",
    "price2_qr",
    "price3_qr",
    "price4_qr",
    "wholesale_level_1_price",
    "wholesale_level_2_price",
    "action_price_qr",
}

BARCODE_FIELDS = {"barcode", "qr_code_barcode"}


def _clean_scalar(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _clean_product_name(value: Any) -> str:
    text = _clean_scalar(value)
    text = re.sub(r"\b0\s*[,.]\s*75\s*([LlЛл])\b", r"0.75\1", text)
    text = re.sub(r"\b0\s+75\s*([LlЛл])\b", r"0.75\1", text)
    text = re.sub(r"\b075\s*([LlЛл])\b", r"0.75\1", text)
    text = re.sub(r"\s+([,.)])", r"\1", text)
    text = re.sub(r"([(])\s+", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalize_price(value: Any) -> str:
    text = _clean_scalar(value)
    if not text or text == ABSENT_VALUE:
        return text

    normalized = text.replace(",", ".").replace(" ", "")
    allowed = "".join(char for char in normalized if char.isdigit() or char == ".")
    if not allowed or allowed.count(".") > 1:
        return text
    try:
        number = float(allowed)
    except ValueError:
        return text

    if "." in allowed:
        decimals = len(allowed.rsplit(".", 1)[1])
        decimals = max(2, min(decimals, 4))
        return f"{number:.{decimals}f}"
    return allowed


def normalize_output_row(row: dict) -> dict:
    """Normalize one output row while preserving empty/absent semantics."""
    normalized = normalize_result_row(row)
    cleaned: dict[str, Any] = {}
    for field in OUTPUT_COLUMNS:
        value = normalized.get(field, "")
        if field == "product_name":
            cleaned[field] = _clean_product_name(value)
        elif field in PRICE_FIELDS:
            cleaned[field] = _normalize_price(value)
        elif field in BARCODE_FIELDS:
            text = _clean_scalar(value)
            cleaned[field] = text if text == ABSENT_VALUE else normalize_barcode(text)
        else:
            cleaned[field] = _clean_scalar(value)
    return normalize_result_row(cleaned)


def normalize_output_rows(rows: list[dict]) -> list[dict]:
    """Normalize multiple output rows before CSV export."""
    return [normalize_output_row(row) for row in rows]


if __name__ == "__main__":
    row = normalize_output_row({"product_name": "A\nB 0. 75L", "price_card": "1 631,99"})
    assert row["product_name"] == "A B 0.75L"
    assert row["price_card"] == "1631.99"
    print("output normalizer self-check passed")

"""Load organizer-provided reference CSV rows for matching."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.schema import ABSENT_VALUE
from src.text_normalization import normalize_product_tokens
from src.utils.barcode import normalize_barcode


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class ReferenceItem:
    raw: dict[str, Any]
    filename: str
    product_name: str
    product_tokens: set[str]
    price_default: float | None
    price_card: float | None
    price_discount: str
    barcode: str
    discount_amount: str
    id_sku: str
    print_datetime: str
    code: str
    additional_info: str
    color: str
    special_symbols: str
    qr_code_barcode: str
    price1_qr: float | None
    price2_qr: float | None
    price3_qr: float | None
    price4_qr: float | None


def resolve_project_path(path: str | Path) -> Path:
    """Resolve a path relative to the project root."""
    result = Path(path)
    if result.is_absolute():
        return result
    return PROJECT_ROOT / result


def parse_price_value(value: Any) -> float | None:
    """Parse a price-like CSV value into float."""
    text = str(value or "").strip()
    if not text or text == ABSENT_VALUE:
        return None
    text = text.replace(",", ".").replace(" ", "")
    text = "".join(char for char in text if char.isdigit() or char == ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _string(row: dict[str, Any], field: str) -> str:
    return str(row.get(field, "") or "").strip()


def _build_reference_item(row: dict[str, Any]) -> ReferenceItem:
    product_name = _string(row, "product_name")
    return ReferenceItem(
        raw=dict(row),
        filename=_string(row, "filename"),
        product_name=product_name,
        product_tokens=normalize_product_tokens(product_name),
        price_default=parse_price_value(row.get("price_default")),
        price_card=parse_price_value(row.get("price_card")),
        price_discount=_string(row, "price_discount"),
        barcode=normalize_barcode(_string(row, "barcode")),
        discount_amount=_string(row, "discount_amount"),
        id_sku=normalize_barcode(_string(row, "id_sku")),
        print_datetime=_string(row, "print_datetime"),
        code=_string(row, "code"),
        additional_info=_string(row, "additional_info"),
        color=_string(row, "color"),
        special_symbols=_string(row, "special_symbols"),
        qr_code_barcode=normalize_barcode(_string(row, "qr_code_barcode")),
        price1_qr=parse_price_value(row.get("price1_qr")),
        price2_qr=parse_price_value(row.get("price2_qr")),
        price3_qr=parse_price_value(row.get("price3_qr")),
        price4_qr=parse_price_value(row.get("price4_qr")),
    )


def load_reference_csv(path: str | Path) -> list[ReferenceItem]:
    """Load reference CSV rows into normalized ReferenceItem objects."""
    csv_path = resolve_project_path(path)
    with csv_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        return [_build_reference_item(row) for row in reader]

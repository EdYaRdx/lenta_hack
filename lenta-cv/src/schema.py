"""Output CSV schema helpers for recognized Lenta price tags."""

from typing import Any


OUTPUT_COLUMNS: list[str] = [
    "filename",
    "product_name",
    "price_default",
    "price_card",
    "price_discount",
    "barcode",
    "discount_amount",
    "id_sku",
    "print_datetime",
    "code",
    "additional_info",
    "color",
    "special_symbols",
    "frame_timestamp",
    "x_min",
    "y_min",
    "x_max",
    "y_max",
    "qr_code_barcode",
    "price1_qr",
    "price2_qr",
    "price3_qr",
    "price4_qr",
    "wholesale_level_1_count",
    "wholesale_level_1_price",
    "wholesale_level_2_count",
    "wholesale_level_2_price",
    "action_price_qr",
    "action_code_qr",
]

ABSENT_VALUE = "\u043d\u0435\u0442"


def empty_result_row() -> dict[str, str]:
    """Return an empty result row with all output columns."""
    return {column: "" for column in OUTPUT_COLUMNS}


def normalize_result_row(row: dict[str, Any]) -> dict[str, Any]:
    """Return a row containing only output columns in the schema order."""
    return {column: row.get(column, "") for column in OUTPUT_COLUMNS}


def mark_absent_fields(row: dict[str, Any], absent_fields: list[str]) -> dict[str, Any]:
    """Mark known absent fields as absent and normalize the result row."""
    normalized = normalize_result_row(row)

    for field in absent_fields:
        if field in normalized:
            normalized[field] = ABSENT_VALUE

    return normalize_result_row(normalized)


if __name__ == "__main__":
    print(empty_result_row())

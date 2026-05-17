"""Build final CSV result rows from extracted fields and tag metadata."""

from typing import Any

from src.schema import ABSENT_VALUE, OUTPUT_COLUMNS, empty_result_row, normalize_result_row
from src.tag_info import TagInfo, tag_info_to_dict


ABSENT_FIELDS_BY_FAMILY: dict[str, set[str]] = {
    "gm_6x6_regular": {
        "price_discount",
        "discount_amount",
        "wholesale_level_1_count",
        "wholesale_level_1_price",
        "wholesale_level_2_count",
        "wholesale_level_2_price",
        "action_price_qr",
        "action_code_qr",
    },
    "gm_6x6_red_promo": {
        "price_discount",
        "wholesale_level_1_count",
        "wholesale_level_1_price",
        "wholesale_level_2_count",
        "wholesale_level_2_price",
        "action_price_qr",
        "action_code_qr",
    },
}


def _as_tag_info_dict(tag_info: TagInfo | dict | None) -> dict[str, Any]:
    if tag_info is None:
        return {}
    return tag_info_to_dict(tag_info)


def _fill_recognized_fields(row: dict[str, Any], fields: dict | None) -> None:
    if not fields:
        return

    for field, value in fields.items():
        if field in OUTPUT_COLUMNS:
            row[field] = value


def _fill_reference_fields(row: dict[str, Any], reference_fields: dict | None) -> None:
    if not reference_fields:
        return

    for field, value in reference_fields.items():
        if field in OUTPUT_COLUMNS and row.get(field, "") == "":
            row[field] = value


def _mark_absent_fields(row: dict[str, Any], family: str) -> None:
    for field in ABSENT_FIELDS_BY_FAMILY.get(family, set()):
        if field in row and row.get(field, "") == "":
            row[field] = ABSENT_VALUE


def build_result_row(
    extracted_fields: dict,
    tag_info: dict | None = None,
    reference_fields: dict | None = None,
) -> dict:
    """Build a normalized output row and mark fields absent for the tag family."""
    row = empty_result_row()
    _fill_recognized_fields(row, extracted_fields)
    _fill_reference_fields(row, reference_fields)

    tag_info_dict = _as_tag_info_dict(tag_info)
    family = tag_info_dict.get("family", "unknown")
    _mark_absent_fields(row, family)

    return normalize_result_row(row)


if __name__ == "__main__":
    extracted_fields = {
        "filename": "price_02.png",
        "price_card": 1029.99,
        "price_default": 1284.29,
        "barcode": "2099999089583",
        "id_sku": "430601060367",
    }
    tag_info = {
        "family": "gm_6x6_regular",
    }
    row = build_result_row(extracted_fields, tag_info)

    assert row["price_card"] == 1029.99
    assert row["price_default"] == 1284.29
    assert row["barcode"] == "2099999089583"
    assert row["price_discount"] == ABSENT_VALUE
    assert row["discount_amount"] == ABSENT_VALUE
    assert row["wholesale_level_1_count"] == ABSENT_VALUE
    assert row["action_price_qr"] == ABSENT_VALUE
    assert row["qr_code_barcode"] == ""

    print(row)

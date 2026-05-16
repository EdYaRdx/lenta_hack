"""Validate decoded QR fields against visible OCR fields."""

import csv
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EMPTY_MARKERS = {"", "нет"}


def resolve_project_path(path: str | Path) -> Path:
    """Resolve relative paths from the project root."""
    result = Path(path)
    if result.is_absolute():
        return result
    return PROJECT_ROOT / result


def _clean_value(value: Any) -> str:
    return str(value or "").strip()


def _parse_price(value: Any) -> float | None:
    text = _clean_value(value)
    if not text or text.lower() == "нет":
        return None
    text = text.replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _price_match(visible_value: Any, qr_value: Any, unit_type: str, notes: list[str]) -> bool | None:
    visible_price = _parse_price(visible_value)
    qr_price = _parse_price(qr_value)
    if visible_price is None or qr_price is None:
        return None

    if abs(visible_price - qr_price) <= 0.01:
        return True

    if unit_type == "100g" or abs((qr_price / 10) - visible_price) <= 0.01:
        if abs((qr_price / 10) - visible_price) <= 0.01:
            notes.append("qr price appears to be per kg while visible price is per 100g")
            return True

    return False


def _field_match(visible_value: Any, qr_value: Any) -> bool | None:
    visible = _clean_value(visible_value)
    qr = _clean_value(qr_value)
    if qr.lower() in EMPTY_MARKERS:
        return None
    if not visible:
        return None
    return visible == qr


def validate_qr_vs_visible_fields(row: dict, tag_info: dict | None = None) -> dict:
    """Compare QR-derived values with visible OCR fields."""
    tag_info = tag_info or {}
    unit_type = str(tag_info.get("unit_type", "") or "")
    notes: list[str] = []

    barcode_match = _field_match(row.get("barcode", ""), row.get("qr_code_barcode", ""))
    price1_match = _price_match(row.get("price_default", ""), row.get("price1_qr", ""), unit_type, notes)
    price2_match = _price_match(row.get("price_card", ""), row.get("price2_qr", ""), unit_type, notes)

    return {
        "barcode_match": barcode_match,
        "price1_match": price1_match,
        "price2_match": price2_match,
        "notes": notes,
    }


def _format_match(value: bool | None) -> str:
    if value is None:
        return ""
    return "true" if value else "false"


def _unique_notes(notes: list[str]) -> list[str]:
    unique = []
    for note in notes:
        if note not in unique:
            unique.append(note)
    return unique


def build_qr_validation_report(
    result_csv_path: str | Path = "outputs/result.csv",
    output_path: str | Path = "outputs/qr_validation_report.csv",
) -> None:
    """Write a CSV report comparing decoded QR values with visible fields."""
    result_path = resolve_project_path(result_csv_path)
    report_path = resolve_project_path(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with result_path.open("r", encoding="utf-8-sig", newline="") as input_file:
        rows = list(csv.DictReader(input_file))

    fieldnames = [
        "filename",
        "barcode",
        "qr_code_barcode",
        "barcode_match",
        "price_default",
        "price1_qr",
        "price1_match",
        "price_card",
        "price2_qr",
        "price2_match",
        "notes",
    ]

    with report_path.open("w", encoding="utf-8-sig", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            validation = validate_qr_vs_visible_fields(row)
            writer.writerow({
                "filename": row.get("filename", ""),
                "barcode": row.get("barcode", ""),
                "qr_code_barcode": row.get("qr_code_barcode", ""),
                "barcode_match": _format_match(validation["barcode_match"]),
                "price_default": row.get("price_default", ""),
                "price1_qr": row.get("price1_qr", ""),
                "price1_match": _format_match(validation["price1_match"]),
                "price_card": row.get("price_card", ""),
                "price2_qr": row.get("price2_qr", ""),
                "price2_match": _format_match(validation["price2_match"]),
                "notes": "; ".join(_unique_notes(validation["notes"])),
            })

    print(f"Saved QR validation report: {report_path}")


if __name__ == "__main__":
    build_qr_validation_report()

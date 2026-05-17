"""Check recognized CSV results against expected clean price-tag baselines."""

import csv
import argparse
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PRICE_FIELDS = {"price_default", "price_card", "price1_qr", "price2_qr", "price3_qr", "price4_qr"}
TEXT_FIELDS = {"product_name"}
STRICT_FIELDS = {
    "barcode",
    "id_sku",
    "print_datetime",
    "additional_info",
    "price_discount",
    "discount_amount",
    "wholesale_level_1_count",
    "wholesale_level_1_price",
    "wholesale_level_2_count",
    "wholesale_level_2_price",
    "action_price_qr",
    "action_code_qr",
}


def resolve_project_path(path: str | Path) -> Path:
    """Resolve relative paths from the project root."""
    result = Path(path)
    if result.is_absolute():
        return result
    return PROJECT_ROOT / result


def load_csv_by_filename(path: str | Path) -> dict[str, dict]:
    """Load CSV rows keyed by filename."""
    resolved_path = resolve_project_path(path)
    with resolved_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return {
            row.get("filename", ""): row
            for row in reader
            if row.get("filename", "")
        }


def normalize_value(value: str) -> str:
    """Normalize a scalar CSV value for strict comparison."""
    return str(value or "").strip()


def normalize_price(value: str) -> str:
    """Normalize a price value to a two-decimal string when possible."""
    normalized = normalize_value(value).replace(" ", "").replace(",", ".")
    if not normalized:
        return ""
    if normalized.lower() == "нет":
        return normalized
    return f"{float(normalized):.2f}"


def soft_normalize_text(value: str) -> str:
    """Normalize product text for tolerant comparisons."""
    normalized = normalize_value(value).lower().replace("ё", "е")
    normalized = normalized.replace(":", ".")
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\s+([,.)])", r"\1", normalized)
    normalized = re.sub(r"([(])\s+", r"\1", normalized)
    normalized = re.sub(r"[\"'`]+", "", normalized)
    return normalized.strip()


def compare_field(expected: str, actual: str, field_name: str) -> bool:
    """Compare one field using field-specific tolerance."""
    if field_name in PRICE_FIELDS:
        if normalize_value(expected).lower() == "нет" or normalize_value(actual).lower() == "нет":
            return normalize_value(expected) == normalize_value(actual)
        try:
            expected_price = float(normalize_price(expected))
            actual_price = float(normalize_price(actual))
        except ValueError:
            return normalize_value(expected) == normalize_value(actual)
        return abs(expected_price - actual_price) <= 0.01

    if field_name in TEXT_FIELDS:
        expected_text = soft_normalize_text(expected)
        actual_text = soft_normalize_text(actual)
        if expected_text == actual_text:
            return True
        return SequenceMatcher(None, expected_text, actual_text).ratio() >= 0.90

    return normalize_value(expected) == normalize_value(actual)


def _print_report(
    expected_path: Path,
    actual_path: Path,
    expected_rows: dict[str, dict],
    actual_rows: dict[str, dict],
    field_totals: dict[str, int],
    field_matches: dict[str, int],
    mismatches: list[dict[str, Any]],
) -> None:
    print(f"Checking {actual_path} against {expected_path}")
    print()

    missing_rows = [
        filename for filename in expected_rows
        if filename not in actual_rows
    ]
    print("Rows:")
    print(f"expected: {len(expected_rows)}")
    print(f"actual matched: {len(expected_rows) - len(missing_rows)}")
    print(f"missing actual rows: {len(missing_rows)}")
    print()

    print("Field accuracy:")
    for field_name in field_totals:
        print(f"{field_name}: {field_matches[field_name]}/{field_totals[field_name]}")

    if mismatches:
        print()
        print("Mismatches:")
        for mismatch in mismatches:
            print(f"- {mismatch['filename']} {mismatch['field']}:")
            print(f"  expected: {mismatch['expected']}")
            print(f"  actual:   {mismatch['actual']}")


def check_results(
    expected_path: str | Path = "data/expected/gm_6x6_regular_expected.csv",
    actual_path: str | Path = "outputs/result.csv",
) -> dict:
    """Compare actual result CSV with the expected clean GM 6x6 baseline."""
    resolved_expected_path = resolve_project_path(expected_path)
    resolved_actual_path = resolve_project_path(actual_path)

    expected_rows = load_csv_by_filename(resolved_expected_path)
    actual_rows = load_csv_by_filename(resolved_actual_path)
    fields = [
        field for field in next(iter(expected_rows.values())).keys()
        if field != "filename"
    ] if expected_rows else []

    field_totals = {field: 0 for field in fields}
    field_matches = {field: 0 for field in fields}
    mismatches: list[dict[str, Any]] = []

    for filename, expected_row in expected_rows.items():
        actual_row = actual_rows.get(filename)
        if actual_row is None:
            mismatches.append({
                "filename": filename,
                "field": "<row>",
                "expected": "present",
                "actual": "missing",
            })
            continue

        for field_name in fields:
            expected_value = expected_row.get(field_name, "")
            actual_value = actual_row.get(field_name, "")
            field_totals[field_name] += 1
            if compare_field(expected_value, actual_value, field_name):
                field_matches[field_name] += 1
            else:
                mismatches.append({
                    "filename": filename,
                    "field": field_name,
                    "expected": expected_value,
                    "actual": actual_value,
                })

    _print_report(
        resolved_expected_path,
        resolved_actual_path,
        expected_rows,
        actual_rows,
        field_totals,
        field_matches,
        mismatches,
    )

    return {
        "expected_rows": len(expected_rows),
        "actual_matched": sum(1 for filename in expected_rows if filename in actual_rows),
        "missing_actual_rows": sum(1 for filename in expected_rows if filename not in actual_rows),
        "field_totals": field_totals,
        "field_matches": field_matches,
        "mismatches": mismatches,
        "ok": not mismatches,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check result CSV against an expected CSV baseline.")
    parser.add_argument(
        "--expected",
        default="data/expected/gm_6x6_regular_expected.csv",
        help="Expected CSV path.",
    )
    parser.add_argument(
        "--actual",
        default="outputs/result.csv",
        help="Actual result CSV path.",
    )
    args = parser.parse_args()
    check_results(expected_path=args.expected, actual_path=args.actual)

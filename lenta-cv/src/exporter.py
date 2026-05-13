"""CSV export helpers for recognized Lenta price tag results."""

import csv
from pathlib import Path
from typing import Any

try:
    from .schema import OUTPUT_COLUMNS, normalize_result_row
except ImportError:
    from schema import OUTPUT_COLUMNS, normalize_result_row


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = "outputs/result.csv"


def resolve_output_path(output_path: str | Path) -> Path:
    """Resolve relative output paths from the project root."""
    path = Path(output_path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def ensure_output_dir(output_path: str | Path) -> Path:
    """Create the CSV parent directory and return the resolved path."""
    path = resolve_output_path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize all rows to the output schema without mutating input rows."""
    return [normalize_result_row(row) for row in rows]


def save_results(
    rows: list[dict[str, Any]],
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    """Save result rows to CSV using the fixed output schema."""
    path = ensure_output_dir(output_path)
    normalized_rows = normalize_rows(rows)

    with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(normalized_rows)

    return path


def append_results(
    rows: list[dict[str, Any]],
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    """Append result rows to CSV, creating the file with headers if needed."""
    path = ensure_output_dir(output_path)
    normalized_rows = normalize_rows(rows)
    file_exists = path.exists()

    encoding = "utf-8" if file_exists else "utf-8-sig"
    with path.open("a", newline="", encoding=encoding) as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(normalized_rows)

    return path


if __name__ == "__main__":
    examples = [
        {
            "filename": "price_01.jpg",
            "product_name": "Example product",
            "price_default": "399.99",
        },
        {
            "filename": "price_02.jpg",
            "price_card": "299.99",
            "qr_code_barcode": "1234567890123",
        },
    ]

    result_path = save_results(examples)
    print(result_path.resolve())

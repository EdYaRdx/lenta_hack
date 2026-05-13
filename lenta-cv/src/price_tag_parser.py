"""Parse one price tag image into a normalized output schema row."""

from typing import Any

from src.ocr import extract_text
from src.parser import parse_ocr_results
from src.preprocess import preprocess_one_image
from src.schema import empty_result_row, normalize_result_row


def parse_price_tag(
    image_name: str,
    backend_name: str = "easyocr",
    use_processed: bool = True,
    preprocess: bool = True,
) -> dict[str, Any]:
    """Parse one image and return one normalized result row."""
    row = empty_result_row()
    row["filename"] = image_name

    if preprocess:
        try:
            preprocess_one_image(image_name)
        except Exception as error:
            print(f"Preprocessing failed for {image_name}: {error}")

    ocr_results = extract_text(
        image_name,
        backend_name=backend_name,
        use_processed=use_processed,
    )
    parsed = parse_ocr_results(ocr_results)

    if parsed.get("price") is not None:
        row["price_card"] = parsed["price"]
    if parsed.get("date") is not None:
        row["print_datetime"] = parsed["date"]
    if parsed.get("code") is not None:
        row["id_sku"] = parsed["code"]

    return normalize_result_row(row)


def parse_many_price_tags(
    image_names: list[str],
    backend_name: str = "easyocr",
    use_processed: bool = True,
    preprocess: bool = True,
) -> list[dict[str, Any]]:
    """Parse multiple images and keep a blank row for failed items."""
    rows = []

    for image_name in image_names:
        try:
            rows.append(
                parse_price_tag(
                    image_name,
                    backend_name=backend_name,
                    use_processed=use_processed,
                    preprocess=preprocess,
                )
            )
        except Exception as error:
            print(f"Error parsing {image_name}: {error}")
            row = empty_result_row()
            row["filename"] = image_name
            rows.append(normalize_result_row(row))

    return rows


if __name__ == "__main__":
    row = parse_price_tag("price_02.jpg")
    print(row)

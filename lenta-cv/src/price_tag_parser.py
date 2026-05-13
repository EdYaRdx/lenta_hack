"""Parse one price tag image into a normalized output schema row."""

from typing import Any

from src.ocr import extract_text
from src.preprocess import preprocess_one_image
from src.schema import empty_result_row, normalize_result_row
from src.strategy_resolver import resolve_parser
from src.tag_type import classify_price_tag


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
    tag_info = classify_price_tag(ocr_results)
    parser = resolve_parser(tag_info)
    parsed_fields = parser.parse(ocr_results, tag_info)
    row.update(parsed_fields)

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

"""Parse one price tag image into a normalized output schema row."""

from typing import Any

from src.extractors.qr import extract_qr_fields
from src.ocr import RAW_DIR, extract_text, find_processed_image
from src.orientation import choose_best_orientation
from src.preprocess import preprocess_one_image
from src.result_row_builder import build_result_row
from src.schema import empty_result_row, normalize_result_row
from src.strategy_resolver import resolve_parser
from src.tag_type import classify_price_tag


def parse_price_tag(
    image_name: str,
    backend_name: str = "easyocr",
    use_processed: bool = True,
    preprocess: bool = True,
    auto_orient: bool = True,
) -> dict[str, Any]:
    """Parse one image and return one normalized result row."""
    if preprocess:
        try:
            preprocess_one_image(image_name)
        except Exception as error:
            print(f"Preprocessing failed for {image_name}: {error}")

    ocr_results = None
    image_path_for_qr = find_processed_image(image_name) if use_processed else None
    if image_path_for_qr is None:
        image_path_for_qr = RAW_DIR / image_name

    if auto_orient:
        try:
            orientation = choose_best_orientation(str(image_path_for_qr), ocr_backend_name=backend_name)
            image_path_for_qr = orientation["image_path"]
            print(
                f"Selected orientation for {image_name}: "
                f"angle={orientation['angle']} score={orientation['score']}"
            )
            if orientation["angle"] != 0:
                ocr_results = orientation["ocr_results"]
        except Exception as error:
            print(f"Auto-orientation failed for {image_name}: {error}")

    if ocr_results is None:
        ocr_results = extract_text(
            image_name,
            backend_name=backend_name,
            use_processed=use_processed,
        )

    tag_info = classify_price_tag(ocr_results)
    parser = resolve_parser(tag_info)
    parsed_fields = parser.parse(ocr_results, tag_info, image_path=image_path_for_qr)
    extracted_fields = {"filename": image_name}
    extracted_fields.update(parsed_fields)
    extracted_fields.update(extract_qr_fields(image_path_for_qr))

    row = build_result_row(
        extracted_fields=extracted_fields,
        tag_info=tag_info,
        reference_fields=None,
    )

    return normalize_result_row(row)


def parse_many_price_tags(
    image_names: list[str],
    backend_name: str = "easyocr",
    use_processed: bool = True,
    preprocess: bool = True,
    auto_orient: bool = True,
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
                    auto_orient=auto_orient,
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

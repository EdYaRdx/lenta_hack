"""Parse one price tag image into a normalized output schema row."""

from typing import Any
from pathlib import Path

from src.extractors.qr import extract_qr_fields
from src.extractors.visual_meta import extract_color
from src.ocr import RAW_DIR, extract_text, find_processed_image
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
    auto_orient: bool = False,
    raw_image_path: str | Path | None = None,
) -> dict[str, Any]:
    """Parse one image and return one normalized result row."""
    # auto_orient is deprecated: input crops are expected to be already oriented.
    raw_path = Path(raw_image_path) if raw_image_path is not None else RAW_DIR / image_name

    if preprocess and raw_image_path is None:
        try:
            preprocess_one_image(image_name)
        except Exception as error:
            print(f"Preprocessing failed for {image_name}: {error}")

    image_path_for_qr = find_processed_image(image_name) if use_processed and raw_image_path is None else None
    if image_path_for_qr is None:
        image_path_for_qr = raw_path

    detected_color = extract_color(raw_path, None)
    ocr_profile = "red_promo" if detected_color == "red" else "default"

    ocr_results = extract_text(
        image_name,
        backend_name=backend_name,
        use_processed=use_processed and ocr_profile == "default",
        ocr_profile=ocr_profile,
        raw_image_path=raw_path,
    )

    tag_info = classify_price_tag(ocr_results, visual_color=detected_color)
    parser = resolve_parser(tag_info)
    parsed_fields = parser.parse(ocr_results, tag_info, image_path=image_path_for_qr)
    extracted_fields = {"filename": image_name}
    extracted_fields.update(parsed_fields)
    qr_fields = extract_qr_fields(image_path_for_qr)
    extracted_fields.update(qr_fields)

    if tag_info.get("family") == "gm_6x6_red_promo" and not extracted_fields.get("price_default"):
        qr_price1 = extracted_fields.get("price1_qr")
        if qr_price1 and qr_price1 != "нет":
            extracted_fields["price_default"] = qr_price1

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
    auto_orient: bool = False,
    raw_image_paths: list[str | Path] | None = None,
) -> list[dict[str, Any]]:
    """Parse multiple images and keep a blank row for failed items."""
    rows = []

    raw_image_paths = raw_image_paths or [None] * len(image_names)
    for image_name, raw_image_path in zip(image_names, raw_image_paths):
        try:
            rows.append(
                parse_price_tag(
                    image_name,
                    backend_name=backend_name,
                    use_processed=use_processed,
                    preprocess=preprocess,
                    auto_orient=auto_orient,
                    raw_image_path=raw_image_path,
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

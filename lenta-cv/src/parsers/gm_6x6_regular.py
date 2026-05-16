"""Parser for regular GM 6x6 price tags."""

from pathlib import Path
from typing import Any

from src.extractors.additional_info import extract_additional_info
from src.extractors.identifiers import extract_barcode, extract_id_sku, extract_print_datetime
from src.extractors.prices import (
    extract_main_price_by_layout,
    extract_price_near_without_card_label,
)
from src.extractors.product_name import extract_product_name_top_area
from src.extractors.visual_meta import extract_code, extract_color, extract_special_symbols
from src.parser import parse_ocr_results
from src.parsers.base import BasePriceTagParser


def extract_price_card_from_layout(ocr_results: list[dict[str, Any]]) -> float | None:
    """Compatibility wrapper for the old GM 6x6 card-price extractor."""
    return extract_main_price_by_layout(ocr_results)


def extract_price_default_from_layout(ocr_results: list[dict[str, Any]]) -> float | None:
    """Compatibility wrapper for the old GM 6x6 default-price extractor."""
    return extract_price_near_without_card_label(ocr_results)


class Gm6x6RegularParser(BasePriceTagParser):
    """Parse regular GM 6x6 price tags."""

    tag_family = "gm_6x6_regular"

    def parse(
        self,
        ocr_results: list[dict[str, Any]],
        tag_info: dict[str, Any],
        image_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Return fields currently supported for GM 6x6 regular tags."""
        parsed = parse_ocr_results(ocr_results)
        result: dict[str, Any] = {}

        price_card = extract_main_price_by_layout(ocr_results)
        if price_card is not None:
            result["price_card"] = price_card
        elif parsed.get("price") is not None:
            result["price_card"] = parsed["price"]

        price_default = extract_price_near_without_card_label(ocr_results)
        if price_default is not None:
            result["price_default"] = price_default

        product_name = extract_product_name_top_area(ocr_results, tag_info)
        if product_name:
            result["product_name"] = product_name

        id_sku = extract_id_sku(ocr_results, tag_info)
        if id_sku:
            result["id_sku"] = id_sku
        elif parsed.get("code") is not None:
            result["id_sku"] = parsed["code"]

        print_datetime = extract_print_datetime(ocr_results, tag_info)
        if print_datetime:
            result["print_datetime"] = print_datetime
        elif parsed.get("date") is not None:
            result["print_datetime"] = parsed["date"]

        barcode = extract_barcode(ocr_results, tag_info)
        if barcode:
            result["barcode"] = barcode

        additional_info = extract_additional_info(ocr_results, tag_info)
        if additional_info:
            result["additional_info"] = additional_info

        color = extract_color(image_path, tag_info)
        if color:
            result["color"] = color

        special_symbols = extract_special_symbols(ocr_results, tag_info)
        if special_symbols:
            result["special_symbols"] = special_symbols

        code = extract_code(ocr_results, tag_info)
        if code:
            result["code"] = code

        return result


if __name__ == "__main__":
    card_example = [
        {
            "text": "1",
            "confidence": 0.99,
            "bbox": [[90, 330], [120, 330], [120, 490], [90, 490]],
            "source": "easyocr",
        },
        {
            "text": "029",
            "confidence": 0.99,
            "bbox": [[130, 330], [450, 330], [450, 490], [130, 490]],
            "source": "easyocr",
        },
        {
            "text": "99",
            "confidence": 0.99,
            "bbox": [[470, 350], [540, 350], [540, 420], [470, 420]],
            "source": "easyocr",
        },
    ]
    default_example = [
        {
            "text": "\u0411\u0435\u0437 \u043a\u0430\u0440\u0442\u044b \u0437\u0430 1 \u043a\u0433",
            "confidence": 0.99,
            "bbox": [[350, 240], [540, 240], [540, 275], [350, 275]],
            "source": "easyocr",
        },
        {
            "text": "1",
            "confidence": 0.99,
            "bbox": [[420, 280], [440, 280], [440, 330], [420, 330]],
            "source": "easyocr",
        },
        {
            "text": "284",
            "confidence": 0.99,
            "bbox": [[445, 280], [520, 280], [520, 330], [445, 330]],
            "source": "easyocr",
        },
        {
            "text": "29",
            "confidence": 0.99,
            "bbox": [[525, 280], [575, 280], [575, 330], [525, 330]],
            "source": "easyocr",
        },
    ]
    print(extract_price_card_from_layout(card_example))
    print(extract_price_default_from_layout(default_example))

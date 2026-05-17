"""Parser for red promotional GM 6x6 price tags."""

from pathlib import Path
from typing import Any

from src.extractors.identifiers import extract_barcode, extract_id_sku, extract_print_datetime
from src.extractors.red_promo import (
    extract_red_additional_info,
    extract_red_discount_amount,
    extract_red_price_card,
    extract_red_price_default,
    extract_red_product_name,
    extract_red_special_symbols,
)
from src.extractors.visual_meta import extract_code, extract_color
from src.parsers.base import BasePriceTagParser


class Gm6x6RedPromoParser(BasePriceTagParser):
    """Parse red promotional GM 6x6 price tags."""

    tag_family = "gm_6x6_red_promo"

    def parse(
        self,
        ocr_results: list[dict[str, Any]],
        tag_info: dict[str, Any],
        image_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Return fields currently supported for red promo GM 6x6 tags."""
        result: dict[str, Any] = {}

        product_name = extract_red_product_name(ocr_results, tag_info, image_path)
        if product_name:
            result["product_name"] = product_name

        price_default = extract_red_price_default(
            ocr_results,
            image_path=image_path,
            tag_info=tag_info,
        )
        if price_default:
            result["price_default"] = price_default

        price_card = extract_red_price_card(ocr_results)
        if price_card is not None:
            result["price_card"] = price_card

        discount_amount = extract_red_discount_amount(ocr_results)
        if discount_amount:
            result["discount_amount"] = discount_amount

        barcode = extract_barcode(ocr_results, tag_info)
        if barcode:
            result["barcode"] = barcode

        id_sku = extract_id_sku(ocr_results, tag_info)
        if id_sku:
            result["id_sku"] = id_sku

        print_datetime = extract_print_datetime(ocr_results, tag_info)
        if print_datetime:
            result["print_datetime"] = print_datetime

        code = extract_code(ocr_results, tag_info)
        if code:
            result["code"] = code

        additional_info = extract_red_additional_info(ocr_results)
        if additional_info:
            result["additional_info"] = additional_info

        color = extract_color(image_path, tag_info)
        if color:
            result["color"] = color

        special_symbols = extract_red_special_symbols(ocr_results)
        if special_symbols:
            result["special_symbols"] = special_symbols

        return result

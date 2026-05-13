"""Fallback parser for unknown price tag families."""

from typing import Any

from src.parser import parse_ocr_results
from src.parsers.base import BasePriceTagParser


class GenericParser(BasePriceTagParser):
    """Parse unknown price tags with the legacy parser."""

    tag_family = "unknown"

    def parse(self, ocr_results: list[dict[str, Any]], tag_info: dict[str, Any]) -> dict[str, Any]:
        """Return fields supported by the legacy parser."""
        parsed = parse_ocr_results(ocr_results)
        result: dict[str, Any] = {}

        if parsed.get("price") is not None:
            result["price_card"] = parsed["price"]
        if parsed.get("date") is not None:
            result["print_datetime"] = parsed["date"]
        if parsed.get("code") is not None:
            result["id_sku"] = parsed["code"]

        return result

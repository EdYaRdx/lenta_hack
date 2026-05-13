"""Identifier extraction placeholders."""


def extract_id_sku(ocr_results: list[dict], tag_info: dict | None = None) -> str:
    """Return SKU identifier extracted from OCR results."""
    # TODO: extract id_sku from bottom OCR blocks and known labels
    return ""


def extract_print_datetime(ocr_results: list[dict], tag_info: dict | None = None) -> str:
    """Return print datetime extracted from OCR results."""
    # TODO: extract print date/time from bottom OCR blocks
    return ""


def extract_barcode(ocr_results: list[dict], tag_info: dict | None = None) -> str:
    """Return barcode extracted from OCR results."""
    # TODO: extract barcode-like long numeric blocks
    return ""

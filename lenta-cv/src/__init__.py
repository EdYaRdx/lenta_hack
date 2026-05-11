"""Core modules for OCR, preprocessing, and parsing."""

_EXPORTS = {
    "extract_text": "src.ocr",
    "ocr_one_image": "src.ocr",
    "get_backend": "src.ocr",
    "find_processed_image": "src.ocr",
    "preprocess_one_image": "src.preprocess",
    "preprocess_all_images": "src.preprocess",
    "read_image": "src.preprocess",
    "to_gray": "src.preprocess",
    "resize_image": "src.preprocess",
    "threshold_image": "src.preprocess",
    "parse_ocr_results": "src.parser",
    "extract_price_from_results": "src.parser",
    "extract_date_from_results": "src.parser",
    "extract_product_code_from_results": "src.parser",
    "extract_price": "src.parser",
    "check_price": "src.checker",
    "run_pipeline": "src.pipeline",
}

__all__ = list(_EXPORTS)


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f"module 'src' has no attribute {name!r}")

    from importlib import import_module

    module = import_module(_EXPORTS[name])
    value = getattr(module, name)
    globals()[name] = value
    return value

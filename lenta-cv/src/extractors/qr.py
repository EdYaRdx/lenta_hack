"""QR-code extraction helpers."""

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote_plus, urlparse

import cv2
import numpy as np

from src.utils.barcode import is_valid_ean13, normalize_barcode


PROJECT_ROOT = Path(__file__).resolve().parents[2]
QR_DEBUG_DIR = PROJECT_ROOT / "outputs" / "qr_debug"
ABSENT_VALUE = "нет"

QR_OUTPUT_FIELDS = [
    "qr_code_barcode",
    "price1_qr",
    "price2_qr",
    "price3_qr",
    "price4_qr",
    "wholesale_level_1_count",
    "wholesale_level_1_price",
    "wholesale_level_2_count",
    "wholesale_level_2_price",
    "action_price_qr",
    "action_code_qr",
]

QR_KEY_MAP = {
    "barcode": "qr_code_barcode",
    "b": "qr_code_barcode",
    "price1": "price1_qr",
    "p1": "price1_qr",
    "price2": "price2_qr",
    "p2": "price2_qr",
    "price3": "price3_qr",
    "p3": "price3_qr",
    "price4": "price4_qr",
    "p4": "price4_qr",
    "wholesalelevel1count": "wholesale_level_1_count",
    "wl1c": "wholesale_level_1_count",
    "wholesalelevel1price": "wholesale_level_1_price",
    "wl1p": "wholesale_level_1_price",
    "wholesalelevel2count": "wholesale_level_2_count",
    "wl2c": "wholesale_level_2_count",
    "wholesalelevel2price": "wholesale_level_2_price",
    "wl2p": "wholesale_level_2_price",
    "actionprice": "action_price_qr",
    "ap": "action_price_qr",
    "actioncode": "action_code_qr",
    "ac": "action_code_qr",
}

_LAST_DEBUG: dict[str, Any] = {}
_LAST_PARSED_DEBUG: dict[str, Any] = {}

QR_PRICE_FIELDS = {
    "price1_qr",
    "price2_qr",
    "price3_qr",
    "price4_qr",
    "wholesale_level_1_price",
    "wholesale_level_2_price",
    "action_price_qr",
}


def _resolve_path(image_path: str | Path) -> Path:
    path = Path(image_path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _safe_name(name: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in name)


def _to_gray(image):
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def add_white_padding(image, pad_ratio: float = 0.15):
    """Return image with a white quiet-zone border around it."""
    height, width = image.shape[:2]
    pad = max(8, int(max(height, width) * pad_ratio))
    if len(image.shape) == 2:
        value = 255
    else:
        value = [255, 255, 255]
    return cv2.copyMakeBorder(
        image,
        pad,
        pad,
        pad,
        pad,
        cv2.BORDER_CONSTANT,
        value=value,
    )


def _crop_with_bbox(image, name: str, bbox: tuple[int, int, int, int]) -> dict:
    height, width = image.shape[:2]
    x_min, y_min, x_max, y_max = bbox
    x_min = max(0, min(width, x_min))
    x_max = max(0, min(width, x_max))
    y_min = max(0, min(height, y_min))
    y_max = max(0, min(height, y_max))
    if x_max <= x_min or y_max <= y_min:
        return {}
    return {
        "name": name,
        "image": image[y_min:y_max, x_min:x_max],
        "bbox": (x_min, y_min, x_max, y_max),
    }


def _black_white_density(gray_roi) -> float:
    if gray_roi.size == 0:
        return 0.0
    _, threshold = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    black_ratio = float(np.mean(threshold == 0))
    white_ratio = float(np.mean(threshold == 255))
    return min(black_ratio, white_ratio)


def find_qr_candidate_rois(image) -> list[dict]:
    """Return heuristic QR ROI candidates from an image."""
    height, width = image.shape[:2]
    candidates = [
        _crop_with_bbox(image, "top_right_45", (int(width * 0.55), 0, width, int(height * 0.45))),
        _crop_with_bbox(image, "top_right_60", (int(width * 0.45), 0, width, int(height * 0.60))),
        _crop_with_bbox(image, "right_half", (int(width * 0.50), 0, width, height)),
        _crop_with_bbox(image, "full_image", (0, 0, width, height)),
    ]

    gray = _to_gray(image)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    adaptive = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        3,
    )
    contours, _hierarchy = cv2.findContours(
        adaptive,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    contour_candidates = []
    image_area = width * height
    for contour in contours:
        x, y, roi_width, roi_height = cv2.boundingRect(contour)
        if roi_width < width * 0.06 or roi_height < height * 0.06:
            continue
        if roi_width * roi_height > image_area * 0.35:
            continue
        aspect = roi_width / max(roi_height, 1)
        if not 0.65 <= aspect <= 1.45:
            continue

        roi_gray = gray[y:y + roi_height, x:x + roi_width]
        density = _black_white_density(roi_gray)
        if density < 0.12:
            continue

        pad_x = int(roi_width * 0.20)
        pad_y = int(roi_height * 0.20)
        contour_candidates.append((
            y,
            x,
            _crop_with_bbox(
                image,
                f"contour_{x}_{y}_{roi_width}x{roi_height}",
                (x - pad_x, y - pad_y, x + roi_width + pad_x, y + roi_height + pad_y),
            ),
        ))

    contour_candidates = sorted(contour_candidates, key=lambda item: (item[0], -item[1]))
    candidates.extend(candidate for _y, _x, candidate in contour_candidates[:8])

    deduplicated = []
    seen = set()
    for candidate in candidates:
        if not candidate:
            continue
        bbox = candidate["bbox"]
        if bbox in seen:
            continue
        seen.add(bbox)
        deduplicated.append(candidate)

    return deduplicated


def build_qr_decode_variants(image) -> list[dict]:
    """Build QR decoding image variants for one ROI."""
    variants = [{"name": "raw", "image": image}]
    gray = _to_gray(image)
    variants.append({"name": "gray", "image": gray})

    for scale in (2, 4, 6):
        variants.append({
            "name": f"upscale_x{scale}",
            "image": cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC),
        })

    gray_x4 = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    variants.append({"name": "clahe_gray_upscale_x4", "image": clahe.apply(gray_x4)})

    _, otsu = cv2.threshold(gray_x4, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append({"name": "threshold_otsu_upscale_x4", "image": otsu})

    adaptive = cv2.adaptiveThreshold(
        gray_x4,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        41,
        5,
    )
    variants.append({"name": "adaptive_threshold_upscale_x4", "image": adaptive})
    variants.append({"name": "inverted_threshold_upscale_x4", "image": cv2.bitwise_not(otsu)})

    return variants


def try_decode_qr_image(image) -> str:
    """Try OpenCV QR decoding for one image variant."""
    detector = cv2.QRCodeDetector()
    payload, _points, _straight = detector.detectAndDecode(image)
    if payload:
        return payload.strip()

    if hasattr(detector, "detectAndDecodeMulti"):
        try:
            ok, decoded_info, _points, _straight = detector.detectAndDecodeMulti(image)
        except cv2.error:
            ok = False
            decoded_info = []
        if ok:
            for item in decoded_info:
                if item:
                    return item.strip()

    return ""


def _write_debug_report(
    image_path: Path,
    decoded: bool,
    payload: str,
    best_roi: str,
    best_variant: str,
    attempts: list[str],
    parsed_fields: dict | None = None,
    unknown_fields: dict | None = None,
    invalid_fields: dict | None = None,
) -> None:
    QR_DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    debug_path = QR_DEBUG_DIR / f"{image_path.stem}_qr_debug.txt"
    lines = [
        f"file: {image_path.name}",
        f"decoded: {'yes' if decoded else 'no'}",
        f"best_roi: {best_roi}",
        f"best_variant: {best_variant}",
        "raw payload:",
        payload,
    ]
    if decoded:
        lines.append("parsed fields:")
        for key, value in (parsed_fields or {}).items():
            lines.append(f"{key}={value}")
        lines.append("unknown fields:")
        for key, value in (unknown_fields or {}).items():
            lines.append(f"{key}={value}")
        lines.append("invalid fields:")
        for key, value in (invalid_fields or {}).items():
            lines.append(f"{key}={value}")
    if not decoded:
        lines.append("attempts:")
        lines.extend(f"- {attempt}" for attempt in attempts)
    debug_path.write_text("\n".join(lines), encoding="utf-8")


def _save_success_image(image_path: Path, roi_name: str, variant_name: str, image) -> None:
    QR_DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    output_path = (
        QR_DEBUG_DIR
        / f"{image_path.stem}_qr_success_{_safe_name(roi_name)}_{_safe_name(variant_name)}.png"
    )
    cv2.imwrite(str(output_path), image)


def decode_qr_payload(image_path: str | Path) -> str:
    """Decode a QR payload from full image and QR candidate ROIs."""
    resolved_path = _resolve_path(image_path)
    image = cv2.imread(str(resolved_path))
    attempts: list[str] = []

    global _LAST_DEBUG
    _LAST_DEBUG = {
        "image_path": resolved_path,
        "decoded": False,
        "payload": "",
        "best_roi": "",
        "best_variant": "",
        "attempts": attempts,
    }

    if image is None:
        _write_debug_report(resolved_path, False, "", "", "", ["image_not_read"])
        return ""

    rois = find_qr_candidate_rois(image)
    for roi in rois:
        padded_roi = add_white_padding(roi["image"])
        for variant in build_qr_decode_variants(padded_roi):
            attempt_name = f"{roi['name']}::{variant['name']}"
            attempts.append(attempt_name)
            payload = try_decode_qr_image(variant["image"])
            if payload:
                _LAST_DEBUG = {
                    "image_path": resolved_path,
                    "decoded": True,
                    "payload": payload,
                    "best_roi": roi["name"],
                    "best_variant": variant["name"],
                    "attempts": attempts,
                }
                _write_debug_report(
                    resolved_path,
                    True,
                    payload,
                    roi["name"],
                    variant["name"],
                    attempts,
                )
                _save_success_image(resolved_path, roi["name"], variant["name"], variant["image"])
                return payload

    _write_debug_report(resolved_path, False, "", "", "", attempts)
    return ""


def _normalize_key(key: str) -> str:
    return key.strip().lower()


def normalize_qr_price(value: str) -> str:
    """Normalize QR price values by removing grouping spaces."""
    stripped = str(value or "").strip().replace(",", ".")
    candidate = stripped.replace(" ", "")
    if candidate.count(".") <= 1 and all(char.isdigit() or char == "." for char in candidate):
        return candidate
    return stripped


def _normalize_qr_value(value: Any) -> str:
    normalized = str(value).strip()
    normalized = unquote_plus(normalized)
    normalized = normalized.replace(",", ".")
    return normalized.strip()


def _flatten_json_pairs(data: Any) -> list[tuple[str, Any]]:
    if isinstance(data, dict):
        pairs = []
        for key, value in data.items():
            if isinstance(value, dict):
                pairs.extend(_flatten_json_pairs(value))
            else:
                pairs.append((str(key), value))
        return pairs
    return []


def _payload_pairs(payload: str) -> list[tuple[str, Any]]:
    stripped = payload.strip()
    if not stripped:
        return []

    if stripped.startswith("{"):
        try:
            return _flatten_json_pairs(json.loads(stripped))
        except json.JSONDecodeError:
            pass

    parsed_url = urlparse(stripped)
    query = parsed_url.query if parsed_url.query else stripped
    query = query.replace(";", "&").replace("\n", "&").replace("\r", "&")

    return parse_qsl(query, keep_blank_values=True)


def parse_qr_payload(payload: str) -> dict:
    """Parse QR payload into output CSV field names."""
    parsed: dict[str, str] = {}
    unknown_fields: dict[str, str] = {}
    invalid_fields: dict[str, str] = {}

    for key, value in _payload_pairs(payload):
        normalized_key = _normalize_key(key)
        output_field = QR_KEY_MAP.get(normalized_key)
        normalized_value = _normalize_qr_value(value)
        if output_field is None:
            unknown_fields[str(key)] = normalized_value
            continue

        if output_field == "qr_code_barcode":
            barcode = normalize_barcode(normalized_value)
            if is_valid_ean13(barcode):
                parsed[output_field] = barcode
            else:
                invalid_fields[str(key)] = normalized_value
            continue

        if output_field in QR_PRICE_FIELDS:
            parsed[output_field] = normalize_qr_price(normalized_value)
        else:
            parsed[output_field] = normalized_value

    global _LAST_PARSED_DEBUG
    _LAST_PARSED_DEBUG = {
        "parsed_fields": parsed,
        "unknown_fields": unknown_fields,
        "invalid_fields": invalid_fields,
    }
    return parsed


def extract_unknown_qr_fields(payload: str) -> dict:
    """Return QR payload fields that are not mapped to output columns."""
    unknown_fields: dict[str, str] = {}
    for key, value in _payload_pairs(payload):
        if QR_KEY_MAP.get(_normalize_key(key)) is None:
            unknown_fields[str(key)] = _normalize_qr_value(value)
    return unknown_fields


def extract_qr_fields(image_path: str | Path) -> dict:
    """Extract QR fields from an image, marking absent QR params when decoded."""
    payload = decode_qr_payload(image_path)
    if not payload:
        return {}

    parsed = parse_qr_payload(payload)
    debug_info = _LAST_PARSED_DEBUG

    result = {}
    for field in QR_OUTPUT_FIELDS:
        value = parsed.get(field, "")
        result[field] = value if value else ABSENT_VALUE
    if "qr_code_barcode" not in parsed and debug_info.get("invalid_fields"):
        result["qr_code_barcode"] = ""

    resolved_path = _resolve_path(image_path)
    _write_debug_report(
        resolved_path,
        True,
        payload,
        _LAST_DEBUG.get("best_roi", ""),
        _LAST_DEBUG.get("best_variant", ""),
        _LAST_DEBUG.get("attempts", []),
        parsed_fields=result,
        unknown_fields=debug_info.get("unknown_fields", {}),
        invalid_fields=debug_info.get("invalid_fields", {}),
    )
    return result


if __name__ == "__main__":
    payload = "b=2099999089583&p1=1284.29&p2=1029.99"
    parsed = parse_qr_payload(payload)

    assert parsed["qr_code_barcode"] == "2099999089583"
    assert parsed["price1_qr"] == "1284.29"
    assert parsed["price2_qr"] == "1029.99"

    print(parsed)

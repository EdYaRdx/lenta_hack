"""Auto-orientation helpers for OCR price-tag crops."""

import re
import tempfile
from pathlib import Path
from typing import Any

import cv2

from src.ocr import get_backend, get_ocr_confidence, get_ocr_text
from src.utils.price import normalize_digits


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ORIENTED_DIR = PROJECT_ROOT / "outputs" / "oriented"


def rotate_image(image, angle: int):
    """Rotate an image by 0, 90, 180, or 270 degrees."""
    if angle == 0:
        return image.copy()
    if angle == 90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    if angle == 180:
        return cv2.rotate(image, cv2.ROTATE_180)
    if angle == 270:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)

    raise ValueError(f"Unsupported rotation angle: {angle}")


def _visible_ocr_items(ocr_results: list[dict]) -> list[dict[str, Any]]:
    items = []
    for item in ocr_results:
        text = get_ocr_text(item).strip()
        if not text or text.startswith("__"):
            continue
        items.append({
            "text": text,
            "lower": text.lower().replace("ё", "е"),
            "confidence": get_ocr_confidence(item),
            "digits": normalize_digits(text),
        })
    return items


def _looks_like_date(text: str) -> bool:
    return bool(re.search(
        r"\b\d{2}[\.\s]\d{2}[\.\s]\d{4}(?:\s+\d{2}[\.: ]?\d{2})?\b",
        text,
    ))


def _has_barcode_group(digit_groups: list[str]) -> bool:
    for index in range(len(digit_groups) - 2):
        lengths = [len(group) for group in digit_groups[index:index + 3]]
        if lengths[0] == 1 and lengths[1] in {5, 6} and lengths[2] == 6:
            return True
    return False


def score_ocr_results(ocr_results: list[dict]) -> float:
    """Score OCR output quality for orientation selection."""
    items = _visible_ocr_items(ocr_results)
    if not items:
        return 0.0

    score = 0.0
    avg_confidence = sum(item["confidence"] for item in items) / len(items)
    score += min(len(items), 24) * 0.8
    score += avg_confidence * 10.0

    text_blob = "\n".join(item["lower"] for item in items)
    keyword_groups = (
        ("с карт", "картой", "по карте"),
        ("без карт", "без карты", "боз карт", "бвз карт", "баз карт", "б8э карт", "ба1 карт"),
        ("цена", "руб", "₽"),
        ("номер", "вес"),
    )
    for group in keyword_groups:
        if any(keyword in text_blob for keyword in group):
            score += 5.0

    if "%" in text_blob or "-%" in text_blob:
        score += 3.0

    date_count = sum(1 for item in items if _looks_like_date(item["lower"]))
    score += min(date_count, 2) * 8.0

    price_like_count = 0
    kopeks_count = 0
    digit_groups = []
    for item in items:
        digits = item["digits"]
        if not digits:
            continue
        digit_groups.append(digits)
        if 2 <= len(digits) <= 4:
            price_like_count += 1
        if len(digits) == 2:
            kopeks_count += 1
        if len(digits) == 13:
            score += 10.0

    score += min(price_like_count, 8) * 2.2
    score += min(kopeks_count, 4) * 1.0
    if _has_barcode_group(digit_groups):
        score += 8.0

    alpha_blocks = [
        item for item in items
        if any(char.isalpha() for char in item["text"])
    ]
    score += min(len(alpha_blocks), 10) * 1.0

    short_noise_count = sum(
        1 for item in items
        if len(item["text"]) <= 2 and not item["digits"]
    )
    if short_noise_count > len(items) * 0.45:
        score -= short_noise_count * 0.8

    return round(score, 4)


def _debug_stem(image_path: Path) -> str:
    stem = image_path.stem
    for suffix in ("_threshold", "_gray"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def _save_oriented_image(image_path: Path, image, angle: int) -> Path:
    ORIENTED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = ORIENTED_DIR / f"{_debug_stem(image_path)}_angle_{angle}.jpg"
    if not cv2.imwrite(str(output_path), image):
        raise OSError(f"Failed to save oriented image: {output_path}")
    return output_path


def choose_best_orientation(image_path: str, ocr_backend_name: str = "easyocr") -> dict[str, Any]:
    """Run OCR on four orientation candidates and return the best one."""
    source_path = Path(image_path)
    image = cv2.imread(str(source_path))
    if image is None:
        raise FileNotFoundError(f"Could not read image for orientation: {source_path}")

    backend = get_backend(ocr_backend_name)
    candidates = []

    with tempfile.TemporaryDirectory(prefix="lenta_orientation_") as temp_dir:
        temp_root = Path(temp_dir)
        for angle in (0, 90, 180, 270):
            rotated = rotate_image(image, angle)
            temp_path = temp_root / f"{source_path.stem}_angle_{angle}.jpg"
            if not cv2.imwrite(str(temp_path), rotated):
                continue

            ocr_results = backend.read(temp_path)
            score = score_ocr_results(ocr_results)
            candidates.append({
                "angle": angle,
                "score": score,
                "ocr_results": ocr_results,
                "rotated_image": rotated,
            })

    if not candidates:
        raise RuntimeError(f"No orientation candidates produced for: {source_path}")

    best = sorted(candidates, key=lambda item: (item["score"], -item["angle"]), reverse=True)[0]
    oriented_path = _save_oriented_image(source_path, best["rotated_image"], best["angle"])

    return {
        "angle": best["angle"],
        "score": best["score"],
        "ocr_results": best["ocr_results"],
        "image_path": str(oriented_path),
    }

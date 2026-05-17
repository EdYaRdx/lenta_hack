"""OCR image variant builders for different price-tag profiles."""

import cv2
import numpy as np


def _to_gray(image):
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _upscale(image, scale: int):
    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def _clahe(gray_image):
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray_image)


def _sharpen(image):
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    return cv2.filter2D(image, -1, kernel)


def _otsu(gray_image):
    _, threshold = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return threshold


def _adaptive(gray_image):
    return cv2.adaptiveThreshold(
        gray_image,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        41,
        7,
    )


def build_ocr_variants_for_profile(image, profile: str = "default") -> list[dict]:
    """Build OCR input variants for a profile."""
    gray = _to_gray(image)

    if profile == "red_promo":
        clahe_gray = _clahe(gray)
        sharpen_gray = _sharpen(gray)
        return [
            {"name": "raw", "image": image},
            {"name": "gray", "image": gray},
            {"name": "upscale_x2_gray", "image": _upscale(gray, 2)},
            {"name": "upscale_x3_gray", "image": _upscale(gray, 3)},
            {"name": "clahe_gray", "image": clahe_gray},
            {"name": "clahe_upscale_x3", "image": _upscale(clahe_gray, 3)},
            {"name": "sharpen_gray", "image": sharpen_gray},
            {"name": "sharpen_upscale_x3", "image": _upscale(sharpen_gray, 3)},
            {"name": "adaptive_threshold", "image": _adaptive(gray)},
            {"name": "otsu_threshold", "image": _otsu(gray)},
        ]

    return [
        {"name": "raw", "image": image},
        {"name": "gray", "image": gray},
        {"name": "upscale_x2_gray", "image": _upscale(gray, 2)},
        {"name": "otsu_threshold", "image": _otsu(gray)},
    ]

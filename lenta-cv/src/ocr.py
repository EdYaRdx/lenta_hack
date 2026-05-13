from pathlib import Path
from functools import lru_cache
from typing import Any, Optional, Protocol

import cv2
import easyocr


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


class OCRBackend(Protocol):
    def read(self, image_path: Path):
        ...


def bbox_to_list(bbox) -> list | None:
    """Convert an OCR bbox to a plain Python list when possible."""
    if bbox is None:
        return None
    if hasattr(bbox, "tolist"):
        return bbox.tolist()
    if isinstance(bbox, (list, tuple)):
        return [bbox_to_list(item) if isinstance(item, (list, tuple)) or hasattr(item, "tolist") else item for item in bbox]
    return bbox


def make_ocr_item(
    text: str,
    confidence: float,
    bbox=None,
    source: str = "easyocr",
) -> dict[str, Any]:
    """Build a normalized OCR result item."""
    return {
        "text": str(text),
        "confidence": float(confidence),
        "bbox": bbox_to_list(bbox),
        "source": source,
    }


def get_ocr_text(item) -> str:
    """Return OCR text from either dict or legacy tuple format."""
    if isinstance(item, dict):
        return str(item.get("text", ""))
    return str(item[0])


def get_ocr_confidence(item) -> float:
    """Return OCR confidence from either dict or legacy tuple format."""
    if isinstance(item, dict):
        return float(item.get("confidence", 0.0))
    return float(item[1])


def get_ocr_bbox(item):
    """Return OCR bbox from dict format, or None for legacy tuples."""
    if isinstance(item, dict):
        return item.get("bbox")
    return None


def ocr_results_to_text(results: list) -> str:
    """Join visible OCR text items with newlines."""
    texts = []
    for item in results:
        text = get_ocr_text(item)
        if text.startswith("__"):
            continue
        texts.append(text)
    return "\n".join(texts)


def cuda_is_available() -> bool:
    """Return whether PyTorch can use a CUDA-capable GPU."""
    try:
        import torch
    except ImportError:
        return False

    return torch.cuda.is_available()


class EasyOCRBackend:
    def __init__(self, languages=None, gpu: Optional[bool] = None):
        self.languages = languages or ["ru", "en"]
        self.gpu = cuda_is_available() if gpu is None else gpu
        self.reader = easyocr.Reader(self.languages, gpu=self.gpu)

    def read(self, image_path: Path):
        raw_results = self.reader.readtext(str(image_path))
        return [
            make_ocr_item(text, confidence, bbox=bbox, source="easyocr")
            for bbox, text, confidence in raw_results
        ]

    def read_digits(self, image):
        raw_results = self.reader.readtext(
            image,
            allowlist="0123456789",
            detail=1,
            paragraph=False,
        )
        return [
            make_ocr_item(text, confidence, bbox=bbox, source="easyocr_digits")
            for bbox, text, confidence in raw_results
        ]


@lru_cache(maxsize=4)
def get_backend(name: str = "easyocr") -> OCRBackend:
    if name.lower() == "easyocr":
        return EasyOCRBackend()

    raise ValueError(f"Неподдерживаемый OCR backend: {name}")


def get_reader() -> easyocr.Reader:
    # Backward-compatible helper for old code paths.
    return easyocr.Reader(["ru", "en"], gpu=cuda_is_available())


def find_processed_image(image_name: str, prefer: str = "threshold") -> Optional[Path]:
    """
    Find preprocessed image in processed directory.
    
    Args:
        image_name: Original image name (e.g., 'price_01.jpg')
        prefer: Prefer 'threshold' or 'gray' version (default: 'threshold')
        
    Returns:
        Path to preprocessed image or None if not found
    """
    stem = Path(image_name).stem
    
    if prefer == "threshold":
        threshold_path = PROCESSED_DIR / f"{stem}_threshold.jpg"
        if threshold_path.exists():
            return threshold_path
        # Fallback to gray
        gray_path = PROCESSED_DIR / f"{stem}_gray.jpg"
        if gray_path.exists():
            return gray_path
    else:
        gray_path = PROCESSED_DIR / f"{stem}_gray.jpg"
        if gray_path.exists():
            return gray_path
        # Fallback to threshold
        threshold_path = PROCESSED_DIR / f"{stem}_threshold.jpg"
        if threshold_path.exists():
            return threshold_path
    
    return None


def ocr_one_image(
    image_path: Path,
    reader: Optional[easyocr.Reader] = None,
    backend: Optional[OCRBackend] = None,
):
    if not image_path.exists():
        raise FileNotFoundError(f"Не найден файл: {image_path}")

    if backend is not None:
        return backend.read(image_path)

    active_reader = reader or get_reader()
    raw_results = active_reader.readtext(str(image_path))

    return [
        make_ocr_item(text, confidence, bbox=bbox, source="easyocr")
        for bbox, text, confidence in raw_results
    ]


def print_ocr_results(results, image_name: str):
    if not results:
        print(f"Текст не найден: {image_name}")
        return

    for item in results:
        text = get_ocr_text(item)
        if text.startswith("__"):
            continue
        confidence = get_ocr_confidence(item)
        print(text, confidence)


def extract_text(image_name: str, backend_name: str = "easyocr", use_processed: bool = True):
    """
    Extract text from image using OCR.
    
    Args:
        image_name: Image filename (e.g., 'price_01.jpg')
        backend_name: OCR backend to use (default: 'easyocr')
        use_processed: Use preprocessed image if available (default: True)
        
    Returns:
        List of OCR result dictionaries with text, confidence, bbox, and source.
    """
    # Try to use preprocessed image if requested
    if use_processed:
        processed_path = find_processed_image(image_name)
        if processed_path:
            print(f"Using preprocessed image: {processed_path.name}")
            image_path = processed_path
        else:
            print(f"Preprocessed image not found, using raw: {image_name}")
            image_path = RAW_DIR / image_name
    else:
        image_path = RAW_DIR / image_name
    
    backend = get_backend(backend_name)
    results = ocr_one_image(image_path, backend=backend)
    if use_processed and isinstance(backend, EasyOCRBackend):
        results.extend(extract_price_hints(RAW_DIR / image_name, backend))
    print_ocr_results(results, image_path.name)
    return results


def extract_price_hints(image_path: Path, backend: EasyOCRBackend):
    image = cv2.imread(str(image_path))
    if image is None:
        return []

    height, width = image.shape[:2]
    crop = image[
        int(height * 0.25):int(height * 0.47),
        int(width * 0.70):int(width * 0.95),
    ]

    hints = []
    for scale in (1, 2, 3):
        resized = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        for item in backend.read_digits(resized):
            text = get_ocr_text(item)
            confidence = get_ocr_confidence(item)
            if confidence >= 0.9 and text.isdigit() and len(text) == 2:
                hints.append(make_ocr_item(
                    f"__kopeks__:{text}",
                    confidence,
                    # TODO: Recalculate digit bbox from scaled crop coordinates
                    # into original image coordinates.
                    bbox=None,
                    source="price_hint",
                ))

    return hints[:1]


if __name__ == "__main__":
    extract_text("price_01.jpg")

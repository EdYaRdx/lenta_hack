from pathlib import Path
from functools import lru_cache
from typing import Optional, Protocol

import cv2
import easyocr


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


class OCRBackend(Protocol):
    def read(self, image_path: Path):
        ...


class EasyOCRBackend:
    def __init__(self, languages=None, gpu: bool = False):
        self.languages = languages or ["ru", "en"]
        self.reader = easyocr.Reader(self.languages, gpu=gpu)

    def read(self, image_path: Path):
        raw_results = self.reader.readtext(str(image_path))
        return [(text, confidence) for _, text, confidence in raw_results]

    def read_digits(self, image):
        raw_results = self.reader.readtext(
            image,
            allowlist="0123456789",
            detail=1,
            paragraph=False,
        )
        return [(text, confidence) for _, text, confidence in raw_results]


@lru_cache(maxsize=4)
def get_backend(name: str = "easyocr") -> OCRBackend:
    if name.lower() == "easyocr":
        return EasyOCRBackend()

    raise ValueError(f"Неподдерживаемый OCR backend: {name}")


def get_reader() -> easyocr.Reader:
    # Backward-compatible helper for old code paths.
    return easyocr.Reader(["ru", "en"], gpu=False)


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

    return [(text, confidence) for _, text, confidence in raw_results]


def print_ocr_results(results, image_name: str):
    if not results:
        print(f"Текст не найден: {image_name}")
        return

    for text, confidence in results:
        if text.startswith("__"):
            continue
        print(text, confidence)


def extract_text(image_name: str, backend_name: str = "easyocr", use_processed: bool = True):
    """
    Extract text from image using OCR.
    
    Args:
        image_name: Image filename (e.g., 'price_01.jpg')
        backend_name: OCR backend to use (default: 'easyocr')
        use_processed: Use preprocessed image if available (default: True)
        
    Returns:
        List of (text, confidence) tuples
    """
    # Try to use preprocessed image if requested
    if use_processed:
        processed_path = find_processed_image(image_name)
        if processed_path:
            print(f"📊 Using preprocessed image: {processed_path.name}")
            image_path = processed_path
        else:
            print(f"⚠️  Preprocessed image not found, using raw: {image_name}")
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
        for text, confidence in backend.read_digits(resized):
            if confidence >= 0.9 and text.isdigit() and len(text) == 2:
                hints.append((f"__kopeks__:{text}", float(confidence)))

    return hints[:1]


if __name__ == "__main__":
    extract_text("price_01.jpg")

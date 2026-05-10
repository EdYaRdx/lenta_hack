from pathlib import Path
from typing import Optional

import easyocr


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"


def get_reader() -> easyocr.Reader:
    return easyocr.Reader(["ru", "en"], gpu=False)


def ocr_one_image(image_path: Path, reader: Optional[easyocr.Reader] = None):
    if not image_path.exists():
        raise FileNotFoundError(f"Не найден файл: {image_path}")

    active_reader = reader or get_reader()
    raw_results = active_reader.readtext(str(image_path))

    return [(text, confidence) for _, text, confidence in raw_results]


def print_ocr_results(results, image_name: str):
    if not results:
        print(f"Текст не найден: {image_name}")
        return

    for text, confidence in results:
        print(text, confidence)


def extract_text(image_name: str):
    image_path = RAW_DIR / image_name

    results = ocr_one_image(image_path)
    print_ocr_results(results, image_path.name)
    return results


if __name__ == "__main__":
    extract_text("price_01.jpg")
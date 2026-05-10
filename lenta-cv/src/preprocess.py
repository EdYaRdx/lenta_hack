from pathlib import Path

import cv2


# Корень проекта: lenta-cv/
PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def read_image(image_path: Path):
    image = cv2.imread(str(image_path))

    if image is None:
        raise FileNotFoundError(f"Не удалось прочитать изображение: {image_path}")

    return image


def to_gray(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def resize_image(image, scale: float = 2.0):
    return cv2.resize(image, None, fx=scale, fy=scale)


def threshold_image(gray_image):
    _, threshold = cv2.threshold(
        gray_image,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    return threshold


def preprocess_one_image(image_name: str):
    input_path = RAW_DIR / image_name

    image = read_image(input_path)

    gray = to_gray(image)
    gray_resized = resize_image(gray, scale=2.0)
    threshold = threshold_image(gray_resized)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    stem = Path(image_name).stem

    gray_output_path = PROCESSED_DIR / f"{stem}_gray.jpg"
    threshold_output_path = PROCESSED_DIR / f"{stem}_threshold.jpg"

    cv2.imwrite(str(gray_output_path), gray_resized)
    cv2.imwrite(str(threshold_output_path), threshold)

    print(f"Сохранено: {gray_output_path}")
    print(f"Сохранено: {threshold_output_path}")


def preprocess_all_images():
    image_paths = sorted(
        path for path in RAW_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )

    if not image_paths:
        print(f"В папке {RAW_DIR} не найдено изображений")
        return

    for image_path in image_paths:
        print(f"Обрабатываю: {image_path.name}")
        preprocess_one_image(image_path.name)


if __name__ == "__main__":
    preprocess_all_images()
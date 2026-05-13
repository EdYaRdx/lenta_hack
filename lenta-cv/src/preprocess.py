"""Image preprocessing helpers for Lenta price tag OCR."""

from pathlib import Path

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def read_image(image_path: Path):
    """Read an image from disk with OpenCV."""
    image = cv2.imread(str(image_path))

    if image is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    return image


def to_gray(image):
    """Convert a BGR image to grayscale."""
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def resize_image(image, scale: float = 2.0):
    """Resize an image by a scale factor."""
    return cv2.resize(image, None, fx=scale, fy=scale)


def threshold_image(gray_image):
    """Apply Otsu binary thresholding to a grayscale image."""
    _, threshold = cv2.threshold(
        gray_image,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )

    return threshold


def preprocess_one_image(image_name: str) -> dict[str, Path]:
    """Preprocess one raw image and return saved output paths."""
    input_path = RAW_DIR / image_name

    image = read_image(input_path)

    gray = to_gray(image)
    gray_resized = resize_image(gray, scale=2.0)
    threshold = threshold_image(gray_resized)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    stem = Path(image_name).stem
    gray_output_path = PROCESSED_DIR / f"{stem}_gray.jpg"
    threshold_output_path = PROCESSED_DIR / f"{stem}_threshold.jpg"

    if not cv2.imwrite(str(gray_output_path), gray_resized):
        raise OSError(f"Failed to save image: {gray_output_path}")
    if not cv2.imwrite(str(threshold_output_path), threshold):
        raise OSError(f"Failed to save image: {threshold_output_path}")

    print(f"Saved: {gray_output_path}")
    print(f"Saved: {threshold_output_path}")

    return {
        "gray": gray_output_path,
        "threshold": threshold_output_path,
    }


def preprocess_all_images() -> None:
    """Preprocess all supported images from the raw data directory."""
    image_paths = sorted(
        path for path in RAW_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )

    if not image_paths:
        print(f"No images found in {RAW_DIR}")
        return

    for image_path in image_paths:
        print(f"Processing: {image_path.name}")
        preprocess_one_image(image_path.name)


if __name__ == "__main__":
    preprocess_all_images()

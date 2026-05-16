"""Base parser contract for price tag families."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BasePriceTagParser(ABC):
    """Abstract parser for one price tag family."""

    tag_family: str = "unknown"

    @abstractmethod
    def parse(
        self,
        ocr_results: list[dict[str, Any]],
        tag_info: dict[str, Any],
        image_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Parse OCR results into a partial output row."""
        raise NotImplementedError

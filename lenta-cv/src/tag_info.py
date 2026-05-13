"""Structured tag classification metadata."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class TagInfo:
    """Detected price tag metadata used for parser selection."""

    family: str = "unknown"
    format: str = "unknown"
    mechanic: str = "unknown"
    unit_type: str = "unknown"
    has_card_price: bool = False
    has_default_price: bool = False
    has_scale_number: bool = False
    has_discount: bool = False
    is_child: bool = False
    has_qr: bool = False
    has_barcode: bool = False
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Return tag info as a plain dictionary."""
        return asdict(self)


def tag_info_to_dict(tag_info: TagInfo | dict) -> dict:
    """Return a dict for both TagInfo and already-dict inputs."""
    if isinstance(tag_info, TagInfo):
        return tag_info.to_dict()
    return tag_info

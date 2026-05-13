"""Parser classes for different Lenta price tag families."""

from src.parsers.base import BasePriceTagParser
from src.parsers.generic import GenericParser
from src.parsers.gm_6x6_regular import Gm6x6RegularParser
from src.parsers.registry import get_parser

__all__ = [
    "BasePriceTagParser",
    "GenericParser",
    "Gm6x6RegularParser",
    "get_parser",
]

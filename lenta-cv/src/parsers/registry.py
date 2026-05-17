"""Parser registry for price tag families."""

from src.parsers.base import BasePriceTagParser
from src.parsers.generic import GenericParser
from src.parsers.gm_6x6_regular import Gm6x6RegularParser
from src.parsers.gm_6x6_red_promo import Gm6x6RedPromoParser
from src.tag_info import tag_info_to_dict


PARSER_REGISTRY: dict[str, BasePriceTagParser] = {
    "gm_6x6_regular": Gm6x6RegularParser(),
    "gm_6x6_red_promo": Gm6x6RedPromoParser(),
}


def get_parser(tag_info: dict) -> BasePriceTagParser:
    """Return a parser for tag_info, falling back to GenericParser."""
    family = tag_info_to_dict(tag_info).get("family", "unknown")
    return PARSER_REGISTRY.get(family, GenericParser())

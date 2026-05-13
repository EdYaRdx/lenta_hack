"""Resolve parsing strategies from tag classification metadata."""

from src.parsers.registry import get_parser


def resolve_parser(tag_info: dict):
    """Resolve a parser; later this can combine format, mechanic rules, and fallback."""
    return get_parser(tag_info)

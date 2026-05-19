"""Match noisy OCR result rows against organizer reference data."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Any

from src.reference_store import ReferenceItem, parse_price_value
from src.schema import ABSENT_VALUE, OUTPUT_COLUMNS, normalize_result_row
from src.text_normalization import normalize_product_tokens, normalize_text
from src.utils.barcode import normalize_barcode


PRICE_OUTPUT_FIELDS = {
    "price_default",
    "price_card",
    "price_discount",
    "price1_qr",
    "price2_qr",
    "price3_qr",
    "price4_qr",
    "wholesale_level_1_price",
    "wholesale_level_2_price",
    "action_price_qr",
}

REFERENCE_ENRICH_FIELDS = [
    "product_name",
    "price_default",
    "price_card",
    "price_discount",
    "barcode",
    "discount_amount",
    "id_sku",
    "print_datetime",
    "code",
    "additional_info",
    "color",
    "special_symbols",
    "qr_code_barcode",
    "price1_qr",
    "price2_qr",
    "price3_qr",
    "price4_qr",
    "wholesale_level_1_count",
    "wholesale_level_1_price",
    "wholesale_level_2_count",
    "wholesale_level_2_price",
    "action_price_qr",
    "action_code_qr",
]

MEDIUM_FILL_FIELDS = {
    "barcode",
    "id_sku",
    "code",
    "qr_code_barcode",
    "price1_qr",
    "price2_qr",
    "price3_qr",
    "price4_qr",
    "wholesale_level_1_count",
    "wholesale_level_1_price",
    "wholesale_level_2_count",
    "wholesale_level_2_price",
    "action_price_qr",
    "action_code_qr",
}


@dataclass
class ReferenceMatch:
    matched: bool
    confidence: str
    score: float
    second_score: float
    margin: float
    reference_item: ReferenceItem | None
    reasons: list[str]
    warnings: list[str]
    top_candidates: list[dict[str, Any]]
    used_catalog_product_name: bool = False


def _present(value: Any) -> bool:
    return value not in ("", None, ABSENT_VALUE)


def _same_text(left: Any, right: Any) -> bool:
    return str(left or "").strip().lower() == str(right or "").strip().lower()


def _price_close(left: float | None, right: float | None, tolerance: float) -> bool:
    return left is not None and right is not None and abs(left - right) <= tolerance


def is_suspicious_low_card_price(
    row_price_card: float | None,
    row_price_default: float | None,
    discount_amount: Any,
) -> bool:
    """Return True for OCR prices that likely lost the leading thousands digit."""
    return (
        row_price_default is not None
        and row_price_default >= 1000
        and row_price_card is not None
        and 0 < row_price_card < 200
        and _present(discount_amount)
    )


def generate_price_repair_variants(price_value: float | None) -> list[float]:
    """Generate conservative matching-only price repairs for dropped leading digits."""
    if price_value is None or price_value <= 0:
        return []
    variants = [round(price_value, 2)]
    if price_value < 100:
        variants.extend([round(price_value + 900, 2), round(price_value + 1900, 2)])
    elif price_value < 200:
        variants.extend([round(price_value + 1000, 2), round(price_value + 2000, 2)])
    elif price_value < 1000:
        variants.extend([round(price_value + 1000, 2), round(price_value + 2000, 2)])
    result: list[float] = []
    for variant in variants:
        if variant not in result:
            result.append(variant)
    return result


def _price_card_repair_match(
    row_price_card: float | None,
    item_price_card: float | None,
    suspicious_low: bool,
) -> float | None:
    if not suspicious_low or row_price_card is None or item_price_card is None:
        return None
    for variant in generate_price_repair_variants(row_price_card):
        if abs(variant - row_price_card) <= 0.01:
            continue
        if _price_close(variant, item_price_card, 0.01):
            return variant
    return None


def _normalize_product_name(value: Any) -> str:
    text = normalize_text(str(value or ""))
    text = re.sub(r"\b0\s*[,.]?\s*75\s*l\b", "0.75l", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _product_name_similarity(left: Any, right: Any) -> float:
    left_text = _normalize_product_name(left)
    right_text = _normalize_product_name(right)
    if not left_text or not right_text:
        return 0.0
    if left_text == right_text:
        return 1.0
    return SequenceMatcher(None, left_text, right_text).ratio()


def _score_reference(
    row: dict,
    item: ReferenceItem,
    used_catalog_product_name: bool,
) -> tuple[float, list[str], list[str]]:
    score = 0.0
    reasons: list[str] = []
    warnings: list[str] = []

    row_barcode = normalize_barcode(str(row.get("barcode", "")))
    row_qr_barcode = normalize_barcode(str(row.get("qr_code_barcode", "")))
    row_id_sku = normalize_barcode(str(row.get("id_sku", "")))

    if row_barcode and item.barcode:
        if row_barcode == item.barcode:
            score += 60
            reasons.append("barcode exact match +60")
            reasons.append("barcode_exact_match")
        else:
            score -= 40
            warnings.append("barcode conflict -40")

    if row_qr_barcode and (item.qr_code_barcode or item.barcode):
        if row_qr_barcode in {item.qr_code_barcode, item.barcode}:
            score += 55
            reasons.append("qr barcode exact match +55")
            reasons.append("qr_code_barcode_exact_match")
        else:
            score -= 35
            warnings.append("qr barcode conflict -35")

    if row_id_sku and item.id_sku:
        if row_id_sku == item.id_sku:
            score += 50
            reasons.append("id_sku exact match +50")
            reasons.append("id_sku_exact_match")

    row_price_card = parse_price_value(row.get("price_card"))
    row_price_default = parse_price_value(row.get("price_default"))
    row_discount = str(row.get("discount_amount", "") or "").strip()
    suspicious_low_card = is_suspicious_low_card_price(row_price_card, row_price_default, row_discount)
    if suspicious_low_card:
        warnings.append("price_card_suspicious_low")
    name_similarity = _product_name_similarity(row.get("product_name"), item.product_name)
    name_exact = name_similarity >= 0.999
    name_near = name_similarity >= 0.95

    if name_exact:
        score += 60
        reasons.append("product_name exact +60")
        if used_catalog_product_name:
            reasons.append("catalog_clean_name_exact_match")
    elif name_near:
        score += 50
        reasons.append("product_name near exact (>=0.95) +50")
    price_card_exact = _price_close(row_price_card, item.price_card, 0.01)
    repaired_price_card = _price_card_repair_match(row_price_card, item.price_card, suspicious_low_card)
    if price_card_exact:
        score += 30
        reasons.append("price_card exact +30")
        reasons.append("price_card_exact_match")
    elif repaired_price_card is not None:
        score += 30
        reasons.append(
            f"price_card_repaired_variant_match {row_price_card:.2f} -> {repaired_price_card:.2f} +30"
        )
        reasons.append("price_card_repaired_variant_match")
    elif row_price_card is not None and item.price_card is not None and abs(row_price_card - item.price_card) > 20:
        if suspicious_low_card:
            reasons.append("price_card_suspicious_low_penalty_skipped")
        else:
            score -= 20
            warnings.append("price_card differs strongly -20")

    price_default_exact = _price_close(row_price_default, item.price_default, 0.01)
    price_default_close_1 = _price_close(row_price_default, item.price_default, 1.00)
    if price_default_exact:
        score += 20
        reasons.append("price_default exact +20")
    elif price_default_close_1:
        score += 12
        reasons.append("price_default close within 1.00 +12")
    elif _price_close(row_price_default, item.price_default, 5.00):
        score += 6
        reasons.append("price_default close within 5.00 +6")

    discount_exact = False
    if row_discount and item.discount_amount:
        if _same_text(row_discount, item.discount_amount):
            score += 20
            reasons.append("discount_amount exact +20")
            reasons.append("discount_exact_match")
            discount_exact = True
        else:
            score -= 15
            warnings.append("discount_amount conflict -15")

    color_exact = False
    if _present(row.get("color")) and item.color and _same_text(row.get("color"), item.color):
        score += 8
        reasons.append("color exact +8")
        color_exact = True

    if _present(row.get("price_discount")) and item.price_discount and _same_text(row.get("price_discount"), item.price_discount):
        score += 5
        reasons.append("price_discount exact +5")

    row_tokens = normalize_product_tokens(str(row.get("product_name", "")))
    strong_overlap = {
        token for token in row_tokens & item.product_tokens
        if len(token) >= 4 and any(char.isalpha() for char in token)
    }
    if strong_overlap:
        token_score = min(len(strong_overlap) * 5, 30)
        score += token_score
        reasons.append(f"product token overlap {sorted(strong_overlap)} +{token_score}")
        if len(strong_overlap) >= 2:
            score += 10
            reasons.append("2+ strong product tokens +10")

    for field, bonus in (
        ("additional_info", 5),
        ("special_symbols", 5),
        ("print_datetime", 5),
        ("code", 5),
    ):
        if _present(row.get(field)) and _present(getattr(item, field)) and _same_text(row.get(field), getattr(item, field)):
            score += bonus
            reasons.append(f"{field} exact +{bonus}")

    name_match = name_exact or name_near
    if name_match and (price_card_exact or repaired_price_card is not None):
        score += 15
        reasons.append("product_name+price_card match bonus +15")
    if name_match and discount_exact:
        score += 10
        reasons.append("product_name+discount exact bonus +10")
    if name_match and price_default_close_1:
        score += 10
        reasons.append("product_name+price_default close bonus +10")

    return score, reasons, warnings


def _candidate_dict(item: ReferenceItem, score: float, reasons: list[str]) -> dict[str, Any]:
    return {
        "score": round(score, 3),
        "product_name": item.product_name,
        "barcode": item.barcode,
        "price_default": item.raw.get("price_default", ""),
        "price_card": item.raw.get("price_card", ""),
        "discount_amount": item.discount_amount,
        "reasons": reasons,
    }


def match_reference_row(
    row: dict,
    reference_items: list[ReferenceItem],
    used_catalog_product_name: bool = False,
) -> ReferenceMatch:
    """Find the best reference item for an aggregated result row."""
    if not reference_items:
        return ReferenceMatch(False, "none", 0.0, 0.0, 0.0, None, [], ["no reference items loaded"], [], False)

    scored = []
    for item in reference_items:
        score, reasons, warnings = _score_reference(row, item, used_catalog_product_name)
        scored.append((score, item, reasons, warnings))

    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_item, reasons, warnings = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    margin = best_score - second_score

    row_barcode = normalize_barcode(str(row.get("barcode", "")))
    row_qr_barcode = normalize_barcode(str(row.get("qr_code_barcode", "")))
    row_id_sku = normalize_barcode(str(row.get("id_sku", "")))
    has_exact_id = (
        bool(row_barcode and row_barcode == best_item.barcode)
        or bool(row_qr_barcode and row_qr_barcode in {best_item.qr_code_barcode, best_item.barcode})
        or bool(row_id_sku and row_id_sku == best_item.id_sku)
    )
    if has_exact_id:
        reasons.append("reference_has_exact_identifier")

    name_similarity = _product_name_similarity(row.get("product_name"), best_item.product_name)
    name_match = name_similarity >= 0.95
    row_price_card = parse_price_value(row.get("price_card"))
    row_price_default = parse_price_value(row.get("price_default"))
    row_discount = str(row.get("discount_amount", "") or "").strip()
    suspicious_low_card = is_suspicious_low_card_price(row_price_card, row_price_default, row_discount)
    price_card_exact = _price_close(row_price_card, best_item.price_card, 0.01)
    repaired_price_card = _price_card_repair_match(row_price_card, best_item.price_card, suspicious_low_card)
    price_card_match = price_card_exact or repaired_price_card is not None
    price_default_exact = _price_close(row_price_default, best_item.price_default, 0.01)
    price_default_close_1 = _price_close(row_price_default, best_item.price_default, 1.00)
    discount_exact = bool(row_discount and best_item.discount_amount and _same_text(row_discount, best_item.discount_amount))
    color_exact = bool(_present(row.get("color")) and best_item.color and _same_text(row.get("color"), best_item.color))

    catalog_assisted_high = (
        used_catalog_product_name and name_match and price_card_match and discount_exact and color_exact
    )
    meets_minimum = (name_match and price_card_match) or (name_match and price_default_close_1 and discount_exact)
    strong_price_high = price_card_match and price_default_exact and discount_exact and color_exact
    unique_price_discount_color_high = (
        price_card_match
        and discount_exact
        and color_exact
        and best_score >= 55
        and margin >= 35
    )
    exact_id_strong_conflict = any(
        warning.startswith("barcode conflict") or warning.startswith("qr barcode conflict")
        for warning in warnings
    )

    if has_exact_id and not exact_id_strong_conflict and margin >= 5:
        confidence = "high"
        reasons.append("reference_high_by_exact_identifier")
    elif has_exact_id:
        confidence = "medium"
        warnings.append("reference conflict on exact id match; margin too small")
    elif catalog_assisted_high:
        confidence = "high"
        reasons.append("reference_high_by_catalog_assisted_match")
    elif strong_price_high and margin >= 10:
        confidence = "high"
        reasons.append("reference_high_by_strong_price_discount_color")
    elif unique_price_discount_color_high:
        confidence = "high"
        reasons.append("reference_high_by_unique_price_discount_color")
    elif best_score >= 70 and margin >= 15 and (name_match or has_exact_id) and meets_minimum:
        confidence = "high"
    elif best_score >= 50 and margin >= 10:
        confidence = "medium"
    elif best_score >= 35:
        confidence = "low"
    else:
        confidence = "none"

    if confidence in {"none", "low"}:
        warnings.append("partial_no_confident_match")
        if not has_exact_id and not name_match:
            warnings.append("no_reliable_identifier_or_name_tokens")

    top_candidates = [
        _candidate_dict(item, score, candidate_reasons)
        for score, item, candidate_reasons, _candidate_warnings in scored[:5]
    ]

    return ReferenceMatch(
        matched=confidence != "none",
        confidence=confidence,
        score=round(best_score, 3),
        second_score=round(second_score, 3),
        margin=round(margin, 3),
        reference_item=best_item if confidence != "none" else None,
        reasons=reasons,
        warnings=warnings,
        top_candidates=top_candidates,
        used_catalog_product_name=used_catalog_product_name,
    )


def _is_noisy_product_name(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    allowed = sum(1 for char in text if char.isalnum() or char.isspace() or char in ".,()/-.")
    weird_ratio = 1.0 - allowed / max(len(text), 1)
    return weird_ratio > 0.25 or len(normalize_product_tokens(text)) < 2


def _reference_value(item: ReferenceItem, field: str) -> Any:
    return item.raw.get(field, "")


def format_price_for_output(value: Any) -> str:
    """Format reference price values for CSV output."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text == ABSENT_VALUE:
        return ABSENT_VALUE
    normalized = text.replace(",", ".").replace(" ", "")
    allowed = "".join(char for char in normalized if char.isdigit() or char == ".")
    if not allowed or allowed.count(".") > 1:
        return text
    if "." not in allowed and not allowed.isdigit():
        return text
    try:
        number = float(allowed)
    except ValueError:
        return text
    if "." in allowed:
        decimals = len(allowed.split(".", 1)[1])
        decimals = max(2, min(decimals, 4))
        return f"{number:.{decimals}f}".rstrip("0").rstrip(".") if decimals > 2 else f"{number:.2f}"
    return allowed


def _format_reference_value(field: str, value: Any) -> str:
    if field in PRICE_OUTPUT_FIELDS:
        return format_price_for_output(value)
    if value is None:
        return ""
    return str(value).strip()


def _can_use_reference_value(value: Any, confidence: str) -> tuple[bool, str]:
    text = str(value or "").strip()
    if text == "":
        return False, "reference value is empty"
    if text == ABSENT_VALUE and confidence != "high":
        return False, "medium confidence: do not use absent marker"
    return True, ""


def enrich_row_from_reference(row: dict, match: ReferenceMatch) -> dict:
    """Return a row enriched from a high/medium confidence reference match."""
    enriched, _changes, _skipped = enrich_row_from_reference_with_trace(row, match)
    return enriched


def enrich_row_from_reference_with_trace(
    row: dict,
    match: ReferenceMatch,
) -> tuple[dict, dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return an enriched row plus changed/skipped reference fields."""
    enriched = normalize_result_row(row)
    changes: dict[str, dict[str, Any]] = {}
    skipped: dict[str, dict[str, Any]] = {}
    item = match.reference_item
    if item is None or match.confidence not in {"high", "medium"}:
        return enriched, changes, skipped

    if match.confidence == "high":
        for field in REFERENCE_ENRICH_FIELDS:
            if field in OUTPUT_COLUMNS:
                raw_value = _reference_value(item, field)
                can_use, reason = _can_use_reference_value(raw_value, match.confidence)
                if not can_use:
                    skipped[field] = {
                        "reference_value": "" if raw_value is None else str(raw_value),
                        "reason": reason,
                    }
                    continue
                value = _format_reference_value(field, raw_value)
                if enriched.get(field, "") != value:
                    changes[field] = {
                        "old": enriched.get(field, ""),
                        "new": value,
                        "source": "reference",
                        "reason": "high confidence reference match",
                    }
                enriched[field] = value
        return normalize_result_row(enriched), changes, skipped

    for field in MEDIUM_FILL_FIELDS:
        raw_value = _reference_value(item, field)
        can_use, reason = _can_use_reference_value(raw_value, match.confidence)
        if not can_use:
            skipped[field] = {
                "reference_value": "" if raw_value is None else str(raw_value),
                "reason": reason,
            }
            continue
        value = _format_reference_value(field, raw_value)
        if field in OUTPUT_COLUMNS and not _present(enriched.get(field)):
            if enriched.get(field, "") != value:
                changes[field] = {
                    "old": enriched.get(field, ""),
                    "new": value,
                    "source": "reference",
                    "reason": "medium confidence fill empty field",
                }
            enriched[field] = value

    return normalize_result_row(enriched), changes, skipped


def diff_enriched_fields(before: dict, after: dict) -> dict[str, dict[str, Any]]:
    """Return fields changed by reference enrichment."""
    diff: dict[str, dict[str, Any]] = {}
    for field in OUTPUT_COLUMNS:
        if before.get(field, "") != after.get(field, ""):
            diff[field] = {
                "old": before.get(field, ""),
                "new": after.get(field, ""),
                "source": "reference",
            }
    return diff


def reference_match_to_dict(match: ReferenceMatch) -> dict[str, Any]:
    """Serialize a ReferenceMatch for JSON reports."""
    selected = match.reference_item.raw if match.reference_item else None
    return {
        "matched": match.matched,
        "confidence": match.confidence,
        "score": match.score,
        "second_score": match.second_score,
        "margin": match.margin,
        "selected_reference": selected,
        "reasons": match.reasons,
        "warnings": match.warnings,
        "top_candidates": match.top_candidates,
        "used_catalog_product_name": match.used_catalog_product_name,
    }

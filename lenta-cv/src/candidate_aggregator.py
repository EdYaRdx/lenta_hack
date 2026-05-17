"""Aggregate multiple parsed views into one result row per tag group."""

from collections import Counter, defaultdict
import re
from typing import Any

from src.input_models import ParsedCandidate, TagGroup
from src.result_row_builder import build_result_row
from src.schema import ABSENT_VALUE, OUTPUT_COLUMNS, normalize_result_row
from src.utils.barcode import is_valid_ean13, normalize_barcode


def _is_present(value: Any) -> bool:
    return value not in ("", None)


def _is_recognized(value: Any) -> bool:
    return _is_present(value) and value != ABSENT_VALUE


def _view_path(candidate: ParsedCandidate) -> str:
    return str(candidate.view.image_path)


def _source_trace(
    value: Any,
    candidate: ParsedCandidate | None,
    reason: str,
) -> dict[str, Any]:
    return {
        "value": "" if value is None else str(value),
        "source_view": _view_path(candidate) if candidate else "",
        "source_filename": candidate.view.image_path.name if candidate else "",
        "candidate_score": candidate.quality.get("score", 0) if candidate else 0,
        "reason": reason,
    }


def compute_candidate_quality(row: dict) -> dict:
    """Compute a simple quality score for a parsed view."""
    filled_fields_count = sum(
        1 for value in row.values()
        if _is_recognized(value)
    )

    score = 0
    if _is_recognized(row.get("barcode")):
        score += 5
    if _is_recognized(row.get("qr_code_barcode")):
        score += 5
    if _is_recognized(row.get("price_card")):
        score += 3
    if _is_recognized(row.get("price_default")):
        score += 3
    if _is_recognized(row.get("discount_amount")):
        score += 2
    product_name = str(row.get("product_name", "")).strip()
    if len(product_name.split()) >= 2:
        score += 2
    if _is_recognized(row.get("color")):
        score += 1
    if _is_recognized(row.get("special_symbols")):
        score += 1
    if _is_recognized(row.get("id_sku")):
        score += 1
    if _is_recognized(row.get("print_datetime")):
        score += 1

    return {
        "filled_fields_count": filled_fields_count,
        "score": score,
        "has_barcode": _is_recognized(row.get("barcode")),
        "has_qr": _is_recognized(row.get("qr_code_barcode")),
    }


def _candidate_sort_key(candidate: ParsedCandidate) -> tuple[int, int]:
    return (
        int(candidate.quality.get("score", 0)),
        int(candidate.quality.get("filled_fields_count", 0)),
    )


def _normal_product_name(value: Any) -> bool:
    text = str(value or "").strip()
    return text != "" and text != ABSENT_VALUE and len(text.split()) >= 2


def score_product_name_value(value: str) -> float:
    """Score product_name readability for grouped aggregation."""
    text = str(value or "").strip()
    if not text or text == ABSENT_VALUE:
        return 0.0

    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", text)
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9./-]*", text)
    useful_words = [word for word in words if len(word) >= 3]
    uppercase_words = [
        word for word in words
        if len(word) >= 3 and any(char.isalpha() for char in word) and word.upper() == word
    ]
    junk_chars = re.findall(r"[#@>={}\[\];|]", text)
    allowed = re.findall(r"[A-Za-zА-Яа-яЁё0-9\s.,()/\-]", text)
    weird_ratio = 1.0 - (len(allowed) / max(len(text), 1))

    score = 0.0
    score += len(letters) * 0.1
    score += len(useful_words) * 1.0
    if letters:
        score += 2.0
    score += min(len(uppercase_words), 4) * 0.5
    score -= len(junk_chars) * 1.5
    if weird_ratio > 0.3:
        score -= weird_ratio * 10.0
    if len(words) > 0:
        one_char_tokens = sum(1 for word in words if len(word) == 1)
        if one_char_tokens / len(words) > 0.35:
            score -= 3.0

    return max(score, 0.0)


def _parse_price(value: Any) -> float | None:
    if not _is_recognized(value):
        return None
    text = str(value).strip().replace(",", ".").replace(" ", "")
    text = re.sub(r"[^0-9.]", "", text)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _format_price(value: float) -> str:
    return f"{value:.2f}"


def _parse_discount(value: Any) -> float | None:
    if not _is_recognized(value):
        return None
    match = re.search(r"(\d{1,2})", str(value))
    if not match:
        return None
    discount = float(match.group(1))
    if discount <= 0 or discount >= 100:
        return None
    return discount / 100.0


def _expected_default_price(price_card: float | None, discount: float | None) -> float | None:
    if price_card is None or discount is None:
        return None
    return price_card / (1.0 - discount)


def _price_close_to_expected(price: float, expected: float, tolerance_ratio: float = 0.08) -> bool:
    tolerance = max(30.0, expected * tolerance_ratio)
    return abs(price - expected) <= tolerance


def _derive_price_candidates_from_numeric_text(value: Any, expected: float | None) -> list[float]:
    """Derive plausible price values from noisy OCR numeric fragments."""
    if expected is None or not _is_recognized(value):
        return []

    digits = re.sub(r"\D", "", str(value))
    if len(digits) < 4:
        return []

    candidates: list[float] = []
    for index in range(0, len(digits) - 3):
        rubles = digits[index:index + 4]
        if rubles.startswith("0"):
            continue
        base = int(rubles)
        for cents in (0, 9, 17, 19, 21, 47, 51, 78, 79, 89, 90, 95, 99):
            candidate = base + cents / 100.0
            if _price_close_to_expected(candidate, expected, tolerance_ratio=0.05):
                candidates.append(candidate)

    return candidates


def choose_consistent_price_default(candidates: list[ParsedCandidate]) -> str:
    """Choose price_default using price_card and discount consistency."""
    value, _trace = choose_consistent_price_default_with_source(candidates)
    return value


def choose_consistent_price_default_with_source(
    candidates: list[ParsedCandidate],
) -> tuple[str, dict[str, Any]]:
    """Choose price_default using price_card/discount consistency with trace."""
    price_card = _parse_price(choose_best_value(candidates, "price_card"))
    discount = _parse_discount(choose_best_value(candidates, "discount_amount"))
    expected = _expected_default_price(price_card, discount)
    if expected is None:
        return choose_best_value_with_source(candidates, "price_default")

    explicit_candidates: list[tuple[float, str, ParsedCandidate]] = []
    derived_candidates: list[tuple[float, str, ParsedCandidate, str]] = []
    for candidate in candidates:
        value = candidate.row.get("price_default")
        parsed = _parse_price(value)
        if parsed is not None:
            explicit_candidates.append((parsed, str(value), candidate))

        for field in ("product_name", "price_default"):
            for derived in _derive_price_candidates_from_numeric_text(candidate.row.get(field), expected):
                derived_candidates.append((
                    _round_price(derived),
                    _format_price(derived),
                    candidate,
                    field,
                ))

    consistent = [
        item for item in explicit_candidates
        if item[0] > (price_card or 0) and _price_close_to_expected(item[0], expected)
    ]
    if consistent:
        best = min(
            consistent,
            key=lambda item: (abs(item[0] - expected), -item[2].quality.get("score", 0)),
        )
        value = _format_price(best[0])
        return value, _source_trace(
            value,
            best[2],
            "selected price_default close to price_card/discount expected value",
        )

    if derived_candidates:
        best = min(
            derived_candidates,
            key=lambda item: (abs(item[0] - expected), -item[2].quality.get("score", 0)),
        )
        value = _format_price(best[0])
        return value, _source_trace(
            value,
            best[2],
            f"derived from {best[3]} numeric text near price_card/discount expected value",
        )

    return "", _source_trace("", None, "no price_default close to price_card/discount expected value")


def _round_price(value: float) -> float:
    return round(value + 1e-9, 2)


def choose_best_value(candidates: list[ParsedCandidate], field: str) -> str:
    """Choose the best field value across parsed candidates."""
    value, _trace = choose_best_value_with_source(candidates, field)
    return value


def _candidate_value_pairs(
    candidates: list[ParsedCandidate],
    field: str,
    *,
    allow_absent: bool = True,
) -> list[tuple[str, ParsedCandidate]]:
    pairs: list[tuple[str, ParsedCandidate]] = []
    for candidate in candidates:
        value = candidate.row.get(field)
        if not _is_present(value):
            continue
        if not allow_absent and value == ABSENT_VALUE:
            continue
        pairs.append((str(value), candidate))
    return pairs


def _choose_by_frequency_or_score(
    pairs: list[tuple[str, ParsedCandidate]],
    reason_prefix: str,
) -> tuple[str, dict[str, Any]]:
    if not pairs:
        return "", _source_trace("", None, "no non-empty value found")

    grouped: dict[str, list[ParsedCandidate]] = defaultdict(list)
    for value, candidate in pairs:
        grouped[value].append(candidate)

    sorted_groups = sorted(
        grouped.items(),
        key=lambda item: (
            len(item[1]),
            max(candidate.quality.get("score", 0) for candidate in item[1]),
            max(candidate.quality.get("filled_fields_count", 0) for candidate in item[1]),
        ),
        reverse=True,
    )
    value, value_candidates = sorted_groups[0]
    best_candidate = max(value_candidates, key=_candidate_sort_key)
    if len(sorted_groups) > 1 and len(sorted_groups[0][1]) == len(sorted_groups[1][1]):
        reason = f"{reason_prefix}; frequency tie, selected from highest-score candidate"
    elif len(value_candidates) > 1:
        reason = f"{reason_prefix}; selected most frequent value ({len(value_candidates)} views)"
    else:
        reason = f"{reason_prefix}; selected best non-empty value"
    return value, _source_trace(value, best_candidate, reason)


def choose_best_value_with_source(
    candidates: list[ParsedCandidate],
    field: str,
) -> tuple[str, dict[str, Any]]:
    """Choose the best field value and return a trace explaining the source."""
    if field == "product_name":
        product_pairs = [
            (str(candidate.row.get(field, "")), candidate)
            for candidate in candidates
            if _normal_product_name(candidate.row.get(field, ""))
        ]
        if not product_pairs:
            return "", _source_trace("", None, "no usable product_name found")
        value, candidate = max(
            product_pairs,
            key=lambda item: (
                score_product_name_value(item[0]),
                item[1].quality.get("score", 0),
                len(item[0]),
            ),
        )
        trace = _source_trace(value, candidate, "selected highest product_name readability score")
        trace["product_name_score"] = round(score_product_name_value(value), 3)
        return value, trace

    if field in {"price_card", "price_default"}:
        pairs = _candidate_value_pairs(candidates, field, allow_absent=False)
        return _choose_by_frequency_or_score(pairs, f"selected {field} by frequency/score")

    if field == "discount_amount":
        pairs = [
            (value, candidate)
            for value, candidate in _candidate_value_pairs(candidates, field, allow_absent=False)
            if re.search(r"-?\d{1,2}\s*%", value) or re.search(r"\d{1,2}", value)
        ]
        return _choose_by_frequency_or_score(pairs, "selected discount_amount by frequency/score")

    if field in {"barcode", "qr_code_barcode"}:
        valid_pairs = []
        invalid_values = []
        for value, candidate in _candidate_value_pairs(candidates, field, allow_absent=False):
            barcode = normalize_barcode(value)
            if is_valid_ean13(barcode):
                valid_pairs.append((barcode, candidate))
            else:
                invalid_values.append(value)
        value, trace = _choose_by_frequency_or_score(valid_pairs, f"selected valid EAN-13 {field}")
        if not value and invalid_values:
            trace["reason"] = f"no valid EAN-13 {field} found; ignored invalid values"
        elif value and len({pair[0] for pair in valid_pairs}) > 1:
            trace["reason"] += "; conflict between different valid barcodes"
        return value, trace

    recognized_pairs = _candidate_value_pairs(candidates, field, allow_absent=False)
    if recognized_pairs:
        return _choose_by_frequency_or_score(recognized_pairs, f"selected {field} by frequency/score")

    absent_pairs = _candidate_value_pairs(candidates, field, allow_absent=True)
    absent_pairs = [(value, candidate) for value, candidate in absent_pairs if value == ABSENT_VALUE]
    if absent_pairs:
        return _choose_by_frequency_or_score(absent_pairs, f"selected absent marker for {field}")

    return "", _source_trace("", None, "no non-empty value found")


def _infer_family(row: dict[str, Any]) -> str:
    color = row.get("color")
    discount = row.get("discount_amount")
    if color == "red" or _is_recognized(discount):
        return "gm_6x6_red_promo"
    if color == "white":
        return "gm_6x6_regular"
    return "unknown"


def _metadata_value(value: Any) -> Any:
    return "" if value is None else value


def aggregate_candidates_with_trace(
    group: TagGroup,
    candidates: list[ParsedCandidate],
) -> tuple[dict, dict[str, dict[str, Any]]]:
    """Aggregate parsed candidates and return field-level source tracing."""
    if not candidates:
        row = normalize_result_row({"filename": group.group_id})
        sources = {
            field: _source_trace(row.get(field, ""), None, "no candidates for group")
            for field in OUTPUT_COLUMNS
        }
        return row, sources

    best_candidate = max(candidates, key=_candidate_sort_key)
    row: dict[str, Any] = {}
    field_sources: dict[str, dict[str, Any]] = {}
    for field in OUTPUT_COLUMNS:
        value, trace = choose_best_value_with_source(candidates, field)
        row[field] = value
        field_sources[field] = trace

    consistent_price_default, price_default_trace = choose_consistent_price_default_with_source(candidates)
    if consistent_price_default:
        row["price_default"] = consistent_price_default
        field_sources["price_default"] = price_default_trace

    first_video_filename = next(
        (view.video_filename for view in group.views if view.video_filename),
        "",
    )
    row["filename"] = first_video_filename or group.group_id
    field_sources["filename"] = _source_trace(
        row["filename"],
        best_candidate if not first_video_filename else None,
        "selected video_filename from metadata" if first_video_filename else "selected group_id fallback",
    )

    metadata_fields = {
        "frame_timestamp": best_candidate.view.frame_timestamp,
        "x_min": best_candidate.view.x_min,
        "y_min": best_candidate.view.y_min,
        "x_max": best_candidate.view.x_max,
        "y_max": best_candidate.view.y_max,
    }
    for field, value in metadata_fields.items():
        row[field] = _metadata_value(value)
        field_sources[field] = _source_trace(
            row[field],
            best_candidate,
            "selected metadata from best overall candidate",
        )

    family = _infer_family(row)
    built_row = build_result_row(
        extracted_fields=row,
        tag_info={"family": family},
        reference_fields=None,
    )
    final_row = normalize_result_row(built_row)
    for field in OUTPUT_COLUMNS:
        if final_row.get(field) != row.get(field) and final_row.get(field) == ABSENT_VALUE:
            field_sources[field] = _source_trace(
                final_row.get(field, ""),
                None,
                f"marked absent by result_row_builder for family {family}",
            )
        else:
            field_sources[field]["value"] = str(final_row.get(field, ""))

    return final_row, field_sources


def aggregate_candidates(group: TagGroup, candidates: list[ParsedCandidate]) -> dict:
    """Aggregate parsed candidates for one tag group into one output row."""
    final_row, _field_sources = aggregate_candidates_with_trace(group, candidates)
    return final_row

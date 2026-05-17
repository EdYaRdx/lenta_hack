"""Group-level pipeline for aggregating multiple views of one price tag."""

import csv
import json
from pathlib import Path
from typing import Any

from src.candidate_aggregator import (
    aggregate_candidates_with_trace,
    compute_candidate_quality,
    score_product_name_value,
)
from src.exporter import save_results
from src.input_loader import load_grouped_input, resolve_project_path
from src.input_models import ParsedCandidate, TagGroup
from src.price_tag_parser import parse_price_tag
from src.reference_matcher import (
    ReferenceMatch,
    enrich_row_from_reference_with_trace,
    match_reference_row,
    reference_match_to_dict,
)
from src.reference_store import ReferenceItem, load_reference_csv
from src.schema import empty_result_row, normalize_result_row


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEBUG_REPORT_PATH = PROJECT_ROOT / "outputs" / "group_debug_report.csv"
REFERENCE_MATCH_REPORT_PATH = PROJECT_ROOT / "outputs" / "reference_match_report.csv"
TRACE_DIR = PROJECT_ROOT / "outputs" / "group_trace"


def _parse_view(group: TagGroup, view) -> ParsedCandidate | None:
    try:
        row = parse_price_tag(
            view.image_path.name,
            preprocess=False,
            raw_image_path=view.image_path,
        )
    except Exception as error:
        print(f"Warning: failed to parse {view.image_path}: {error}")
        return None

    quality = compute_candidate_quality(row)
    return ParsedCandidate(
        group_id=group.group_id,
        view=view,
        row=row,
        quality=quality,
    )


def _empty_group_row(group: TagGroup) -> dict[str, Any]:
    row = empty_result_row()
    row["filename"] = group.group_id
    return normalize_result_row(row)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _write_group_trace(
    group: TagGroup,
    candidates: list[ParsedCandidate],
    final_row: dict[str, Any],
    field_sources: dict[str, dict[str, Any]],
    row_before_reference: dict[str, Any] | None = None,
    reference_match: ReferenceMatch | None = None,
    enriched_fields: dict[str, dict[str, Any]] | None = None,
    skipped_reference_fields: dict[str, dict[str, Any]] | None = None,
) -> Path:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    trace_path = TRACE_DIR / f"{group.group_id}.json"
    payload = {
        "group_id": group.group_id,
        "views_count": len(group.views),
        "final_row": final_row,
        "field_sources": field_sources,
        "row_before_reference": row_before_reference,
        "enriched_fields": enriched_fields or {},
        "skipped_reference_fields": skipped_reference_fields or {},
        "reference_match": reference_match_to_dict(reference_match) if reference_match else None,
        "candidates": [
            {
                "view_path": str(candidate.view.image_path),
                "metadata_path": str(candidate.view.metadata_path) if candidate.view.metadata_path else "",
                "score": candidate.quality.get("score", 0),
                "quality": candidate.quality,
                "row": candidate.row,
            }
            for candidate in candidates
        ],
    }
    trace_path.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )
    return trace_path


def _mark_reference_field_sources(
    field_sources: dict[str, dict[str, Any]],
    enriched_fields: dict[str, dict[str, Any]],
) -> None:
    for field, change in enriched_fields.items():
        field_sources[field] = {
            "value": str(change.get("new", "")),
            "source_view": "reference",
            "source_filename": "",
            "candidate_score": 0,
            "reason": "enriched from reference match",
        }


def _write_reference_match_report(
    groups: list[TagGroup],
    rows_before_reference: dict[str, dict[str, Any]],
    matches_by_group: dict[str, ReferenceMatch],
    skipped_reference_fields_by_group: dict[str, dict[str, dict[str, Any]]],
    trace_paths_by_group: dict[str, Path],
) -> None:
    REFERENCE_MATCH_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "group_id",
        "matched",
        "confidence",
        "score",
        "second_score",
        "margin",
        "selected_product_name",
        "selected_barcode",
        "selected_price_default",
        "selected_price_card",
        "selected_discount_amount",
        "row_product_name",
        "row_price_default",
        "row_price_card",
        "row_discount_amount",
        "reasons",
        "warnings",
        "skipped_reference_fields_count",
        "top_candidates_count",
        "trace_path",
    ]
    with REFERENCE_MATCH_REPORT_PATH.open("w", newline="", encoding="utf-8-sig") as report_file:
        writer = csv.DictWriter(report_file, fieldnames=fieldnames)
        writer.writeheader()
        for group in groups:
            match = matches_by_group.get(group.group_id)
            if match is None:
                continue
            row = rows_before_reference.get(group.group_id, {})
            selected = match.reference_item.raw if match.reference_item else {}
            skipped = skipped_reference_fields_by_group.get(group.group_id, {})
            writer.writerow({
                "group_id": group.group_id,
                "matched": match.matched,
                "confidence": match.confidence,
                "score": match.score,
                "second_score": match.second_score,
                "margin": match.margin,
                "selected_product_name": selected.get("product_name", ""),
                "selected_barcode": selected.get("barcode", ""),
                "selected_price_default": selected.get("price_default", ""),
                "selected_price_card": selected.get("price_card", ""),
                "selected_discount_amount": selected.get("discount_amount", ""),
                "row_product_name": row.get("product_name", ""),
                "row_price_default": row.get("price_default", ""),
                "row_price_card": row.get("price_card", ""),
                "row_discount_amount": row.get("discount_amount", ""),
                "reasons": " | ".join(match.reasons),
                "warnings": " | ".join(match.warnings),
                "skipped_reference_fields_count": len(skipped),
                "top_candidates_count": len(match.top_candidates),
                "trace_path": str(trace_paths_by_group.get(group.group_id, "")),
            })


def _write_group_debug_report(
    groups: list[TagGroup],
    candidates_by_group: dict[str, list[ParsedCandidate]],
    rows: list[dict[str, Any]],
    field_sources_by_group: dict[str, dict[str, dict[str, Any]]],
    trace_paths_by_group: dict[str, Path],
) -> None:
    DEBUG_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows_by_group = {group.group_id: row for group, row in zip(groups, rows)}
    fieldnames = [
        "group_id",
        "views_count",
        "best_view",
        "best_score",
        "filename",
        "product_name",
        "price_default",
        "price_card",
        "discount_amount",
        "barcode",
        "qr_code_barcode",
        "filled_fields_count",
        "product_name_source_view",
        "price_default_source_view",
        "price_card_source_view",
        "discount_amount_source_view",
        "barcode_source_view",
        "qr_code_barcode_source_view",
        "special_symbols_source_view",
        "additional_info_source_view",
        "product_name_score",
        "field_trace_path",
    ]

    with DEBUG_REPORT_PATH.open("w", newline="", encoding="utf-8-sig") as debug_file:
        writer = csv.DictWriter(debug_file, fieldnames=fieldnames)
        writer.writeheader()
        for group in groups:
            candidates = candidates_by_group.get(group.group_id, [])
            best = max(
                candidates,
                key=lambda candidate: (
                    candidate.quality.get("score", 0),
                    candidate.quality.get("filled_fields_count", 0),
                ),
                default=None,
            )
            row = rows_by_group.get(group.group_id, {})
            sources = field_sources_by_group.get(group.group_id, {})

            def source_view(field: str) -> str:
                return str(sources.get(field, {}).get("source_view", ""))

            writer.writerow({
                "group_id": group.group_id,
                "views_count": len(group.views),
                "best_view": str(best.view.image_path) if best else "",
                "best_score": best.quality.get("score", "") if best else "",
                "filename": row.get("filename", ""),
                "product_name": row.get("product_name", ""),
                "price_default": row.get("price_default", ""),
                "price_card": row.get("price_card", ""),
                "discount_amount": row.get("discount_amount", ""),
                "barcode": row.get("barcode", ""),
                "qr_code_barcode": row.get("qr_code_barcode", ""),
                "filled_fields_count": best.quality.get("filled_fields_count", "") if best else "",
                "product_name_source_view": source_view("product_name"),
                "price_default_source_view": source_view("price_default"),
                "price_card_source_view": source_view("price_card"),
                "discount_amount_source_view": source_view("discount_amount"),
                "barcode_source_view": source_view("barcode"),
                "qr_code_barcode_source_view": source_view("qr_code_barcode"),
                "special_symbols_source_view": source_view("special_symbols"),
                "additional_info_source_view": source_view("additional_info"),
                "product_name_score": round(score_product_name_value(str(row.get("product_name", ""))), 3),
                "field_trace_path": str(trace_paths_by_group.get(group.group_id, "")),
            })


def parse_grouped_input(
    input_root: str | Path,
    output_path: str | Path = "outputs/group_result.csv",
    reference_path: str | Path | None = None,
    enable_reference_matching: bool = False,
) -> list[dict]:
    """Parse grouped input and save one aggregated row per tag group."""
    groups = load_grouped_input(input_root)
    if not groups:
        print(f"No tag groups found in {resolve_project_path(input_root)}")
        save_results([], output_path=output_path)
        return []

    reference_items: list[ReferenceItem] = []
    if enable_reference_matching:
        if reference_path is None:
            raise ValueError("Reference matching requires reference_path")
        reference_items = load_reference_csv(reference_path)
        print(f"Loaded reference items: {len(reference_items)}")

    results: list[dict[str, Any]] = []
    candidates_by_group: dict[str, list[ParsedCandidate]] = {}
    field_sources_by_group: dict[str, dict[str, dict[str, Any]]] = {}
    trace_paths_by_group: dict[str, Path] = {}
    rows_before_reference: dict[str, dict[str, Any]] = {}
    matches_by_group: dict[str, ReferenceMatch] = {}
    skipped_reference_fields_by_group: dict[str, dict[str, dict[str, Any]]] = {}
    for group in groups:
        candidates = [
            candidate
            for view in group.views
            if (candidate := _parse_view(group, view)) is not None
        ]
        candidates_by_group[group.group_id] = candidates
        if candidates:
            final_row, field_sources = aggregate_candidates_with_trace(group, candidates)
        else:
            final_row, field_sources = aggregate_candidates_with_trace(group, candidates)
            final_row = _empty_group_row(group)

        row_before_reference = dict(final_row)
        reference_match = None
        enriched_fields: dict[str, dict[str, Any]] = {}
        skipped_reference_fields: dict[str, dict[str, Any]] = {}
        if enable_reference_matching:
            reference_match = match_reference_row(final_row, reference_items)
            enriched_row, enriched_fields, skipped_reference_fields = enrich_row_from_reference_with_trace(
                final_row,
                reference_match,
            )
            if enriched_fields:
                _mark_reference_field_sources(field_sources, enriched_fields)
            final_row = enriched_row
            matches_by_group[group.group_id] = reference_match
            skipped_reference_fields_by_group[group.group_id] = skipped_reference_fields

        results.append(final_row)
        rows_before_reference[group.group_id] = row_before_reference
        field_sources_by_group[group.group_id] = field_sources
        trace_paths_by_group[group.group_id] = _write_group_trace(
            group,
            candidates,
            final_row,
            field_sources,
            row_before_reference=row_before_reference if enable_reference_matching else None,
            reference_match=reference_match,
            enriched_fields=enriched_fields,
            skipped_reference_fields=skipped_reference_fields,
        )

    saved_path = save_results(results, output_path=output_path)
    _write_group_debug_report(
        groups,
        candidates_by_group,
        results,
        field_sources_by_group,
        trace_paths_by_group,
    )
    if enable_reference_matching:
        _write_reference_match_report(
            groups,
            rows_before_reference,
            matches_by_group,
            skipped_reference_fields_by_group,
            trace_paths_by_group,
        )
        print(f"Saved reference match report: {REFERENCE_MATCH_REPORT_PATH}")
    print(f"Saved grouped CSV: {saved_path}")
    print(f"Saved group debug report: {DEBUG_REPORT_PATH}")
    print(f"Processed tag groups: {len(results)}")
    return results


if __name__ == "__main__":
    parse_grouped_input("input/Test3")

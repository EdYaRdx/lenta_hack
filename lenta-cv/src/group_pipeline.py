"""Group-level pipeline for aggregating multiple views of one price tag."""

import csv
import json
from time import perf_counter
from pathlib import Path
from typing import Any

from src.candidate_aggregator import (
    aggregate_candidates_with_trace,
    compute_candidate_quality,
    score_product_name_value,
)
from src.exporter import save_results
from src.input_loader import load_grouped_input, resolve_project_path
from src.input_models import ImageView, ParsedCandidate, TagGroup
from src.ocr_cache import get_ocr_cache_stats, reset_ocr_cache_stats
from src.output_normalizer import normalize_output_row, normalize_output_rows
from src.price_tag_parser import parse_price_tag
from src.product_catalog import (
    ProductCatalogIndex,
    ProductCatalogMatch,
    catalog_match_to_dict,
    enrich_product_name_from_catalog,
    load_product_catalog_index,
    resolve_catalog_conflict_by_tokens,
)
from src.reference_matcher import (
    ReferenceMatch,
    enrich_row_from_reference_with_trace,
    match_reference_row,
    reference_match_to_dict,
)
from src.reference_store import ReferenceItem, load_reference_csv
from src.schema import empty_result_row, normalize_result_row
from src.view_selector import select_initial_views, select_next_views
from src.timing import PipelineTimer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEBUG_REPORT_PATH = PROJECT_ROOT / "outputs" / "group_debug_report.csv"
REFERENCE_MATCH_REPORT_PATH = PROJECT_ROOT / "outputs" / "reference_match_report.csv"
PRODUCT_CATALOG_MATCH_REPORT_PATH = PROJECT_ROOT / "outputs" / "product_catalog_match_report.csv"
TRACE_DIR = PROJECT_ROOT / "outputs" / "group_trace"


def _parse_view(group: TagGroup, view: ImageView, use_ocr_cache: bool = False) -> ParsedCandidate | None:
    try:
        row = parse_price_tag(
            view.image_path.name,
            preprocess=False,
            raw_image_path=view.image_path,
            use_ocr_cache=use_ocr_cache,
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


def _parse_view_batch(
    group: TagGroup,
    views: list[ImageView],
    use_ocr_cache: bool = False,
) -> list[ParsedCandidate]:
    candidates: list[ParsedCandidate] = []
    for view in views:
        candidate = _parse_view(group, view, use_ocr_cache=use_ocr_cache)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _view_key(view: ImageView) -> str:
    return str(view.image_path.resolve())


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
    optimization: dict[str, Any] | None = None,
    row_before_reference: dict[str, Any] | None = None,
    row_after_catalog: dict[str, Any] | None = None,
    row_after_reference: dict[str, Any] | None = None,
    product_catalog_match: ProductCatalogMatch | None = None,
    catalog_enriched_fields: dict[str, dict[str, Any]] | None = None,
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
        "optimization": optimization or {},
        "row_before_reference": row_before_reference,
        "row_after_catalog": row_after_catalog,
        "row_after_reference": row_after_reference,
        "product_catalog_match": catalog_match_to_dict(product_catalog_match),
        "catalog_enriched_fields": catalog_enriched_fields or {},
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


def _mark_catalog_field_sources(
    field_sources: dict[str, dict[str, Any]],
    enriched_fields: dict[str, dict[str, Any]],
) -> None:
    for field, change in enriched_fields.items():
        field_sources[field] = {
            "value": str(change.get("new", "")),
            "source_view": "product_catalog",
            "source_filename": "",
            "candidate_score": 0,
            "reason": str(change.get("reason", "enriched from product catalog")),
        }


def _write_product_catalog_match_report(
    groups: list[TagGroup],
    rows_before_catalog: dict[str, dict[str, Any]],
    matches_by_group: dict[str, ProductCatalogMatch],
    trace_paths_by_group: dict[str, Path],
) -> None:
    PRODUCT_CATALOG_MATCH_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "group_id",
        "matched",
        "confidence",
        "score",
        "second_score",
        "margin",
        "ocr_product_name",
        "selected_fullname",
        "selected_code",
        "distinguishing_tokens",
        "conflict_resolved",
        "conflict_resolution_reason",
        "matched_distinguishing_tokens",
        "reasons",
        "warnings",
        "top_candidates",
    ]
    with PRODUCT_CATALOG_MATCH_REPORT_PATH.open("w", newline="", encoding="utf-8-sig") as report_file:
        writer = csv.DictWriter(report_file, fieldnames=fieldnames)
        writer.writeheader()
        for group in groups:
            match = matches_by_group.get(group.group_id)
            if match is None:
                continue
            selected = match.best_item
            row = rows_before_catalog.get(group.group_id, {})
            resolution = match.conflict_resolution or {}
            writer.writerow({
                "group_id": group.group_id,
                "matched": match.matched,
                "confidence": match.confidence,
                "score": match.score,
                "second_score": match.second_score,
                "margin": match.margin,
                "ocr_product_name": row.get("product_name", ""),
                "selected_fullname": selected.fullname if selected else "",
                "selected_code": selected.code if selected else "",
                "distinguishing_tokens": " | ".join(match.distinguishing_tokens),
                "conflict_resolved": resolution.get("resolved", ""),
                "conflict_resolution_reason": resolution.get("reason", ""),
                "matched_distinguishing_tokens": " | ".join(resolution.get("matched_tokens", [])),
                "reasons": " | ".join(match.reasons),
                "warnings": " | ".join(match.warnings),
                "top_candidates": json.dumps(match.top_candidates, ensure_ascii=False),
            })


def _write_reference_match_report(
    groups: list[TagGroup],
    rows_before_reference: dict[str, dict[str, Any]],
    rows_after_reference: dict[str, dict[str, Any]],
    matches_by_group: dict[str, ReferenceMatch],
    skipped_reference_fields_by_group: dict[str, dict[str, dict[str, Any]]],
    enriched_fields_by_group: dict[str, dict[str, dict[str, Any]]],
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
        "selected_qr_code_barcode",
        "selected_price_default",
        "selected_price_card",
        "selected_discount_amount",
        "row_barcode",
        "row_qr_code_barcode",
        "row_product_name",
        "row_price_default",
        "row_price_card",
        "row_discount_amount",
        "barcode_exact_match",
        "qr_code_barcode_exact_match",
        "id_sku_exact_match",
        "used_catalog_product_name",
        "enriched_product_name",
        "enriched_fields",
        "reasons",
        "warnings",
        "skipped_reference_fields_count",
        "top_candidates_count",
        "top_candidates",
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
            after_reference = rows_after_reference.get(group.group_id, {})
            selected = match.reference_item.raw if match.reference_item else {}
            skipped = skipped_reference_fields_by_group.get(group.group_id, {})
            enriched_fields = enriched_fields_by_group.get(group.group_id, {})
            reasons = set(match.reasons)
            writer.writerow({
                "group_id": group.group_id,
                "matched": match.matched,
                "confidence": match.confidence,
                "score": match.score,
                "second_score": match.second_score,
                "margin": match.margin,
                "selected_product_name": selected.get("product_name", ""),
                "selected_barcode": selected.get("barcode", ""),
                "selected_qr_code_barcode": selected.get("qr_code_barcode", ""),
                "selected_price_default": selected.get("price_default", ""),
                "selected_price_card": selected.get("price_card", ""),
                "selected_discount_amount": selected.get("discount_amount", ""),
                "row_barcode": row.get("barcode", ""),
                "row_qr_code_barcode": row.get("qr_code_barcode", ""),
                "row_product_name": row.get("product_name", ""),
                "row_price_default": row.get("price_default", ""),
                "row_price_card": row.get("price_card", ""),
                "row_discount_amount": row.get("discount_amount", ""),
                "barcode_exact_match": "barcode_exact_match" in reasons,
                "qr_code_barcode_exact_match": "qr_code_barcode_exact_match" in reasons,
                "id_sku_exact_match": "id_sku_exact_match" in reasons,
                "used_catalog_product_name": match.used_catalog_product_name,
                "enriched_product_name": after_reference.get("product_name", ""),
                "enriched_fields": json.dumps(enriched_fields, ensure_ascii=False),
                "reasons": " | ".join(match.reasons),
                "warnings": " | ".join(match.warnings),
                "skipped_reference_fields_count": len(skipped),
                "top_candidates_count": len(match.top_candidates),
                "top_candidates": json.dumps(match.top_candidates, ensure_ascii=False),
                "trace_path": str(trace_paths_by_group.get(group.group_id, "")),
            })


def _write_group_debug_report(
    groups: list[TagGroup],
    candidates_by_group: dict[str, list[ParsedCandidate]],
    rows: list[dict[str, Any]],
    field_sources_by_group: dict[str, dict[str, dict[str, Any]]],
    trace_paths_by_group: dict[str, Path],
    optimization_by_group: dict[str, dict[str, Any]],
    reference_matches_by_group: dict[str, ReferenceMatch] | None = None,
) -> None:
    DEBUG_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows_by_group = {group.group_id: row for group, row in zip(groups, rows)}
    fieldnames = [
        "group_id",
        "views_count",
        "total_views",
        "processed_views",
        "skipped_views",
        "view_selection_enabled",
        "processed_view_paths",
        "early_stopped",
        "early_stop_reason",
        "batch_number_when_stopped",
        "ocr_cache_hits",
        "ocr_cache_misses",
        "group_seconds",
        "ocr_seconds",
        "aggregation_seconds",
        "catalog_match_seconds",
        "reference_match_seconds",
        "normalization_seconds",
        "reference_confidence",
        "reference_score",
        "reference_margin",
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
            optimization = optimization_by_group.get(group.group_id, {})
            match = (reference_matches_by_group or {}).get(group.group_id)

            def source_view(field: str) -> str:
                return str(sources.get(field, {}).get("source_view", ""))

            writer.writerow({
                "group_id": group.group_id,
                "views_count": len(group.views),
                "total_views": optimization.get("total_views", len(group.views)),
                "processed_views": optimization.get("processed_views", len(candidates)),
                "skipped_views": optimization.get("skipped_views", max(len(group.views) - len(candidates), 0)),
                "view_selection_enabled": optimization.get("view_selection_enabled", ""),
                "processed_view_paths": " | ".join(optimization.get("processed_view_paths", [])),
                "early_stopped": optimization.get("early_stopped", ""),
                "early_stop_reason": optimization.get("early_stop_reason", ""),
                "batch_number_when_stopped": optimization.get("batch_number_when_stopped", ""),
                "ocr_cache_hits": optimization.get("cache_hits", ""),
                "ocr_cache_misses": optimization.get("cache_misses", ""),
                "group_seconds": optimization.get("group_seconds", ""),
                "ocr_seconds": optimization.get("ocr_seconds", ""),
                "aggregation_seconds": optimization.get("aggregation_seconds", ""),
                "catalog_match_seconds": optimization.get("catalog_match_seconds", ""),
                "reference_match_seconds": optimization.get("reference_match_seconds", ""),
                "normalization_seconds": optimization.get("normalization_seconds", ""),
                "reference_confidence": match.confidence if match else "",
                "reference_score": match.score if match else "",
                "reference_margin": match.margin if match else "",
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


def _row_has_product_tokens(row: dict[str, Any]) -> bool:
    product_name = str(row.get("product_name", "") or "").strip()
    return len([token for token in product_name.split() if len(token) >= 3]) >= 2


def should_early_stop(match: ReferenceMatch, final_row: dict[str, Any]) -> bool:
    """Return whether the current group has enough evidence to stop OCR-ing views."""
    if match.confidence != "high" or match.score < 70 or match.margin < 15:
        return False
    if not final_row.get("price_card"):
        return False

    has_identity = any(final_row.get(field) for field in ("barcode", "qr_code_barcode", "id_sku"))
    if has_identity:
        return True

    has_product_tokens = _row_has_product_tokens(final_row)
    has_discount_product = bool(final_row.get("discount_amount")) and has_product_tokens
    has_default_product = bool(final_row.get("price_default")) and has_product_tokens
    return has_discount_product or has_default_product


def _limit_batch(batch: list[ImageView], processed_count: int, max_views_per_group: int | None) -> list[ImageView]:
    if max_views_per_group is None:
        return batch
    remaining = max(max_views_per_group - processed_count, 0)
    return batch[:remaining]


def _aggregate_current_candidates(
    group: TagGroup,
    candidates: list[ParsedCandidate],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    if candidates:
        return aggregate_candidates_with_trace(group, candidates)
    final_row, field_sources = aggregate_candidates_with_trace(group, candidates)
    return _empty_group_row(group), field_sources


def parse_grouped_input(
    input_root: str | Path,
    output_path: str | Path = "outputs/group_result.csv",
    reference_path: str | Path | None = None,
    enable_reference_matching: bool = False,
    product_catalog_path: str | Path | None = None,
    use_product_catalog: bool = False,
    use_view_selection: bool = True,
    initial_views: int = 7,
    next_views: int = 5,
    max_views_per_group: int | None = None,
    adaptive: bool = True,
    early_stop: bool = True,
    use_ocr_cache: bool = False,
    use_product_catalog_cache: bool = True,
    rebuild_product_catalog_cache: bool = False,
    timing_enabled: bool = False,
    timing_output_dir: str | Path = "outputs",
) -> list[dict]:
    """Parse grouped input and save one aggregated row per tag group."""
    timer = PipelineTimer() if timing_enabled else None
    total_start = perf_counter() if timer else None

    if timer:
        with timer.section("load_grouped_input"):
            groups = load_grouped_input(input_root)
    else:
        groups = load_grouped_input(input_root)
    if not groups:
        print(f"No tag groups found in {resolve_project_path(input_root)}")
        save_results([], output_path=output_path)
        if timer and total_start is not None:
            timer.add_record("total_run", perf_counter() - total_start)
            output_dir = resolve_project_path(timing_output_dir)
            timer.save_csv(output_dir / "timing_report.csv")
            timer.save_txt(output_dir / "timing_report.txt")
        return []

    reference_items: list[ReferenceItem] = []
    if enable_reference_matching:
        if reference_path is None:
            raise ValueError("Reference matching requires reference_path")
        if timer:
            with timer.section("load_reference"):
                reference_items = load_reference_csv(reference_path)
        else:
            reference_items = load_reference_csv(reference_path)
        print(f"Loaded reference items: {len(reference_items)}")

    product_catalog_index: ProductCatalogIndex | None = None
    if use_product_catalog:
        if product_catalog_path is None:
            raise ValueError("Product catalog matching requires product_catalog_path")
        if timer:
            with timer.section("load_product_catalog"):
                product_catalog_index = load_product_catalog_index(
                    product_catalog_path,
                    use_cache=use_product_catalog_cache,
                    rebuild_cache=rebuild_product_catalog_cache,
                )
        else:
            product_catalog_index = load_product_catalog_index(
                product_catalog_path,
                use_cache=use_product_catalog_cache,
                rebuild_cache=rebuild_product_catalog_cache,
            )
        print(f"Loaded product catalog items: {len(product_catalog_index.items)}")

    results: list[dict[str, Any]] = []
    candidates_by_group: dict[str, list[ParsedCandidate]] = {}
    field_sources_by_group: dict[str, dict[str, dict[str, Any]]] = {}
    trace_paths_by_group: dict[str, Path] = {}
    rows_before_reference: dict[str, dict[str, Any]] = {}
    rows_after_reference: dict[str, dict[str, Any]] = {}
    rows_before_catalog: dict[str, dict[str, Any]] = {}
    catalog_matches_by_group: dict[str, ProductCatalogMatch] = {}
    matches_by_group: dict[str, ReferenceMatch] = {}
    skipped_reference_fields_by_group: dict[str, dict[str, dict[str, Any]]] = {}
    enriched_fields_by_group: dict[str, dict[str, dict[str, Any]]] = {}
    optimization_by_group: dict[str, dict[str, Any]] = {}
    grouped_start = perf_counter() if timer else None
    def _match_catalog_row(
        row: dict[str, Any],
        candidates: list[ParsedCandidate],
    ) -> tuple[dict[str, Any], ProductCatalogMatch | None, dict[str, dict[str, Any]], bool]:
        if not (use_product_catalog and product_catalog_index is not None):
            return row, None, {}, False

        catalog_match = product_catalog_index.search(str(row.get("product_name", "")))
        if catalog_match.confidence == "conflict":
            query_texts = [str(row.get("product_name", ""))]
            query_texts.extend(
                str(candidate.row.get("product_name", ""))
                for candidate in candidates
                if candidate.row.get("product_name")
            )
            top_items = product_catalog_index.top_items_from_candidates(
                catalog_match.top_candidates,
                limit=5,
            )
            catalog_match = resolve_catalog_conflict_by_tokens(
                query_texts,
                top_items,
                catalog_match,
            )

        enriched_row, catalog_changes = enrich_product_name_from_catalog(
            row,
            catalog_match,
        )
        conflict_resolved = bool(
            catalog_match is not None
            and catalog_match.conflict_resolution
            and catalog_match.conflict_resolution.get("resolved")
        )
        return enriched_row, catalog_match, catalog_changes, conflict_resolved

    for group in groups:
        group_start = perf_counter()
        reset_ocr_cache_stats()
        candidates: list[ParsedCandidate] = []
        selected_paths: set[str] = set()
        processed_view_paths: list[str] = []
        early_stopped = False
        early_stop_reason = ""
        stop_batch_number: int | None = None
        batch_number = 0

        if use_view_selection:
            batch = select_initial_views(group.views, limit=initial_views)
        else:
            batch = list(group.views)
        batch = _limit_batch(batch, len(selected_paths), max_views_per_group)

        reference_match = None
        product_catalog_match = None
        catalog_enriched_fields: dict[str, dict[str, Any]] = {}
        used_catalog_product_name = False
        final_row: dict[str, Any] = {}
        field_sources: dict[str, dict[str, Any]] = {}
        row_before_reference: dict[str, Any] = {}
        row_after_catalog: dict[str, Any] = {}
        row_after_reference: dict[str, Any] = {}
        enriched_fields: dict[str, dict[str, Any]] = {}
        skipped_reference_fields: dict[str, Any] = {}
        ocr_seconds = 0.0
        aggregation_seconds = 0.0
        catalog_match_seconds = 0.0
        reference_match_seconds = 0.0
        normalization_seconds = 0.0

        while batch:
            batch_number += 1
            for view in batch:
                key = _view_key(view)
                if key in selected_paths:
                    continue
                selected_paths.add(key)
                processed_view_paths.append(str(view.image_path))

            if timer:
                with timer.section("group_ocr", group_id=group.group_id, batch_views=len(batch)) as record:
                    candidates.extend(_parse_view_batch(group, batch, use_ocr_cache=use_ocr_cache))
                ocr_seconds += record["seconds"]
            else:
                candidates.extend(_parse_view_batch(group, batch, use_ocr_cache=use_ocr_cache))

            if timer:
                with timer.section("group_aggregation", group_id=group.group_id) as record:
                    final_row, field_sources = _aggregate_current_candidates(group, candidates)
                aggregation_seconds += record["seconds"]
            else:
                final_row, field_sources = _aggregate_current_candidates(group, candidates)

            temp_row = final_row
            temp_catalog_match = None
            temp_conflict_resolved = False
            if use_product_catalog and product_catalog_index is not None:
                if timer:
                    with timer.section("group_catalog_match", group_id=group.group_id) as record:
                        temp_row, temp_catalog_match, _temp_changes, temp_conflict_resolved = _match_catalog_row(
                            temp_row,
                            candidates,
                        )
                    catalog_match_seconds += record["seconds"]
                else:
                    temp_row, temp_catalog_match, _temp_changes, temp_conflict_resolved = _match_catalog_row(
                        temp_row,
                        candidates,
                    )

            if enable_reference_matching:
                if timer:
                    with timer.section("group_reference_match", group_id=group.group_id) as record:
                        reference_match = match_reference_row(temp_row, reference_items)
                    reference_match_seconds += record["seconds"]
                else:
                    reference_match = match_reference_row(temp_row, reference_items)
                if early_stop and should_early_stop(reference_match, temp_row):
                    early_stopped = True
                    stop_batch_number = batch_number
                    if batch_number == 1:
                        early_stop_reason = "reference_high_after_initial_batch"
                    elif temp_conflict_resolved:
                        early_stop_reason = "reference_high_after_catalog_conflict_resolution"
                    else:
                        early_stop_reason = "reference_high_after_adaptive_batch"
                    break

            if not (use_view_selection and enable_reference_matching and adaptive):
                break
            if max_views_per_group is not None and len(selected_paths) >= max_views_per_group:
                break
            if len(selected_paths) >= len(group.views):
                break

            next_batch = select_next_views(group.views, selected_paths, limit=next_views)
            batch = _limit_batch(next_batch, len(selected_paths), max_views_per_group)

        candidates_by_group[group.group_id] = candidates
        if not final_row:
            final_row, field_sources = _aggregate_current_candidates(group, candidates)

        if not early_stop:
            early_stop_reason = "disabled"
        elif not early_stopped:
            early_stop_reason = "no_high_match"

        rows_before_catalog[group.group_id] = dict(final_row)
        if use_product_catalog and product_catalog_index is not None:
            if timer:
                with timer.section("group_catalog_match", group_id=group.group_id) as record:
                    final_row, product_catalog_match, catalog_enriched_fields, _conflict_resolved = _match_catalog_row(
                        final_row,
                        candidates,
                    )
                catalog_match_seconds += record["seconds"]
            else:
                final_row, product_catalog_match, catalog_enriched_fields, _conflict_resolved = _match_catalog_row(
                    final_row,
                    candidates,
                )
            if catalog_enriched_fields:
                _mark_catalog_field_sources(field_sources, catalog_enriched_fields)
            if product_catalog_match is not None:
                conflict_resolved = bool(
                    product_catalog_match.conflict_resolution
                    and product_catalog_match.conflict_resolution.get("resolved")
                )
                if product_catalog_match.best_item and (
                    product_catalog_match.confidence == "high" or conflict_resolved
                ):
                    selected_name = product_catalog_match.best_item.fullname
                    current_name = str(final_row.get("product_name", "") or "").strip()
                    used_catalog_product_name = bool(selected_name and current_name == selected_name)
            catalog_matches_by_group[group.group_id] = product_catalog_match

        row_before_reference = dict(final_row)
        row_after_catalog = dict(final_row)
        if enable_reference_matching:
            if timer:
                with timer.section("group_reference_match", group_id=group.group_id) as record:
                    reference_match = match_reference_row(
                        final_row,
                        reference_items,
                        used_catalog_product_name=used_catalog_product_name,
                    )
                    enriched_row, enriched_fields, skipped_reference_fields = enrich_row_from_reference_with_trace(
                        final_row,
                        reference_match,
                    )
                reference_match_seconds += record["seconds"]
            else:
                reference_match = match_reference_row(
                    final_row,
                    reference_items,
                    used_catalog_product_name=used_catalog_product_name,
                )
                enriched_row, enriched_fields, skipped_reference_fields = enrich_row_from_reference_with_trace(
                    final_row,
                    reference_match,
                )
            if enriched_fields:
                _mark_reference_field_sources(field_sources, enriched_fields)
            row_after_reference = dict(enriched_row)
            final_row = enriched_row
            matches_by_group[group.group_id] = reference_match
            skipped_reference_fields_by_group[group.group_id] = skipped_reference_fields
            enriched_fields_by_group[group.group_id] = enriched_fields

        cache_stats = get_ocr_cache_stats()
        catalog_confidence = "none"
        if product_catalog_match is not None:
            conflict_resolved = bool(
                product_catalog_match.conflict_resolution
                and product_catalog_match.conflict_resolution.get("resolved")
            )
            catalog_confidence = "conflict_resolved" if conflict_resolved else product_catalog_match.confidence
        group_seconds = perf_counter() - group_start
        optimization = {
            "total_views": len(group.views),
            "processed_views": len(selected_paths),
            "skipped_views": max(len(group.views) - len(selected_paths), 0),
            "view_selection_enabled": use_view_selection,
            "processed_view_paths": processed_view_paths,
            "early_stopped": early_stopped,
            "early_stop_reason": early_stop_reason,
            "batch_number_when_stopped": stop_batch_number or "",
            "use_ocr_cache": use_ocr_cache,
            "cache_hits": cache_stats.get("hits", 0),
            "cache_misses": cache_stats.get("misses", 0),
            "adaptive": adaptive,
            "max_views_per_group": max_views_per_group if max_views_per_group is not None else "",
            "group_seconds": round(group_seconds, 6),
            "ocr_seconds": round(ocr_seconds, 6),
            "aggregation_seconds": round(aggregation_seconds, 6),
            "catalog_match_seconds": round(catalog_match_seconds, 6),
            "reference_match_seconds": round(reference_match_seconds, 6),
            "normalization_seconds": round(normalization_seconds, 6),
        }
        optimization_by_group[group.group_id] = optimization

        if timer:
            timer.add_record(
                "group_total",
                group_seconds,
                group_id=group.group_id,
                total_views=len(group.views),
                processed_views=len(selected_paths),
                skipped_views=max(len(group.views) - len(selected_paths), 0),
                early_stopped=early_stopped,
                reference_confidence=reference_match.confidence if reference_match else "",
                catalog_confidence=catalog_confidence,
                ocr_seconds=round(ocr_seconds, 6),
                cache_hits=cache_stats.get("hits", 0),
                cache_misses=cache_stats.get("misses", 0),
            )

        if timer:
            with timer.section("group_normalization", group_id=group.group_id) as record:
                final_row = normalize_output_row(final_row)
            normalization_seconds += record["seconds"]
        else:
            final_row = normalize_output_row(final_row)
        results.append(final_row)
        rows_before_reference[group.group_id] = row_before_reference
        rows_after_reference[group.group_id] = row_after_reference or dict(final_row)
        field_sources_by_group[group.group_id] = field_sources
        trace_paths_by_group[group.group_id] = _write_group_trace(
            group,
            candidates,
            final_row,
            field_sources,
            optimization=optimization,
            row_before_reference=row_before_reference if enable_reference_matching else None,
            row_after_catalog=row_after_catalog if enable_reference_matching else None,
            row_after_reference=row_after_reference if enable_reference_matching else None,
            product_catalog_match=product_catalog_match,
            catalog_enriched_fields=catalog_enriched_fields,
            reference_match=reference_match,
            enriched_fields=enriched_fields,
            skipped_reference_fields=skipped_reference_fields,
        )

    results = normalize_output_rows(results)
    if timer:
        with timer.section("export"):
            saved_path = save_results(results, output_path=output_path)
    else:
        saved_path = save_results(results, output_path=output_path)
    _write_group_debug_report(
        groups,
        candidates_by_group,
        results,
        field_sources_by_group,
        trace_paths_by_group,
        optimization_by_group,
        matches_by_group,
    )
    if enable_reference_matching:
        _write_reference_match_report(
            groups,
            rows_before_reference,
            rows_after_reference,
            matches_by_group,
            skipped_reference_fields_by_group,
            enriched_fields_by_group,
            trace_paths_by_group,
        )
        print(f"Saved reference match report: {REFERENCE_MATCH_REPORT_PATH}")
    if use_product_catalog:
        _write_product_catalog_match_report(
            groups,
            rows_before_catalog,
            catalog_matches_by_group,
            trace_paths_by_group,
        )
        print(f"Saved product catalog match report: {PRODUCT_CATALOG_MATCH_REPORT_PATH}")
    print(f"Saved grouped CSV: {saved_path}")
    print(f"Saved group debug report: {DEBUG_REPORT_PATH}")
    print(f"Processed tag groups: {len(results)}")
    if timer:
        if grouped_start is not None:
            timer.add_record("grouped_processing", perf_counter() - grouped_start)
        if total_start is not None:
            timer.add_record("total_run", perf_counter() - total_start)
        output_dir = resolve_project_path(timing_output_dir)
        timer.save_csv(output_dir / "timing_report.csv")
        timer.save_txt(output_dir / "timing_report.txt")
        summary = timer.summary()
        total_seconds = summary.get("total_seconds", 0.0)
        processed_views = sum(item.get("processed_views", 0) for item in optimization_by_group.values())
        total_views = sum(item.get("total_views", 0) for item in optimization_by_group.values())
        avg_per_view = (total_seconds / processed_views) if processed_views else 0.0
        slowest_group = summary.get("slowest_group", "")
        slowest_seconds = summary.get("slowest_group_seconds", 0.0)
        print("Timing:")
        print(f"- total: {total_seconds:.2f} sec")
        print(f"- groups: {len(results)}")
        print(f"- processed views: {processed_views} / {total_views}")
        print(f"- avg per processed view: {avg_per_view:.4f} sec")
        if slowest_group:
            print(f"- slowest group: {slowest_group}, {slowest_seconds:.2f} sec")
        print(f"- timing report: {output_dir / 'timing_report.txt'}")
    return results


if __name__ == "__main__":
    parse_grouped_input("input/Test3")

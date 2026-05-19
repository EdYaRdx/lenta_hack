"""Build summary reports for the grouped pipeline."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"
SUMMARY_CSV_PATH = OUTPUT_DIR / "pipeline_summary_report.csv"
SUMMARY_TXT_PATH = OUTPUT_DIR / "pipeline_summary_report.txt"
TIMING_REPORT_PATH = OUTPUT_DIR / "timing_report.csv"


def resolve_project_path(path: str | Path) -> Path:
    result = Path(path)
    if result.is_absolute():
        return result
    return PROJECT_ROOT / result


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        print(f"Warning: report not found: {path}")
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        return list(reader)


def _safe_int(value: Any) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def _safe_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes", "y"}


def _is_empty(value: Any) -> bool:
    return str(value or "").strip() == ""


def _is_noisy_product_name(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    allowed = sum(1 for char in text if char.isalnum() or char.isspace() or char in ".,()/-.\"'")
    weird_ratio = 1.0 - allowed / max(len(text), 1)
    if weird_ratio > 0.25:
        return True
    tokens = re.findall(r"[A-Za-zА-Яа-я0-9]+", text)
    return len(tokens) < 2


def _load_json(value: Any) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def build_pipeline_summary(
    group_result_path: str | Path = "outputs/group_result.csv",
    group_debug_path: str | Path = "outputs/group_debug_report.csv",
    reference_report_path: str | Path = "outputs/reference_match_report.csv",
    catalog_report_path: str | Path = "outputs/product_catalog_match_report.csv",
    trace_dir: str | Path = "outputs/group_trace",
) -> dict[str, Any]:
    group_result_path = resolve_project_path(group_result_path)
    group_debug_path = resolve_project_path(group_debug_path)
    reference_report_path = resolve_project_path(reference_report_path)
    catalog_report_path = resolve_project_path(catalog_report_path)
    trace_dir = resolve_project_path(trace_dir)

    group_rows = _read_csv_rows(group_result_path)
    debug_rows = _read_csv_rows(group_debug_path)
    reference_rows = _read_csv_rows(reference_report_path)
    catalog_rows = _read_csv_rows(catalog_report_path)
    timing_rows = _read_csv_rows(TIMING_REPORT_PATH)

    group_ids = {row.get("filename", "") for row in group_rows if row.get("filename")}
    group_ids.update(row.get("group_id", "") for row in debug_rows if row.get("group_id"))
    group_ids.update(row.get("group_id", "") for row in reference_rows if row.get("group_id"))
    group_ids.update(row.get("group_id", "") for row in catalog_rows if row.get("group_id"))
    if trace_dir.exists():
        group_ids.update(path.stem for path in trace_dir.glob("*.json"))

    reference_confidence_by_group = {
        row.get("group_id", ""): str(row.get("confidence", "")).strip().lower()
        for row in reference_rows
        if row.get("group_id")
    }

    total_views = sum(_safe_int(row.get("total_views")) for row in debug_rows)
    processed_views = sum(_safe_int(row.get("processed_views")) for row in debug_rows)
    skipped_views = sum(_safe_int(row.get("skipped_views")) for row in debug_rows)
    early_stopped_count = sum(1 for row in debug_rows if _safe_bool(row.get("early_stopped")))
    ocr_cache_hits = sum(_safe_int(row.get("ocr_cache_hits")) for row in debug_rows)
    ocr_cache_misses = sum(_safe_int(row.get("ocr_cache_misses")) for row in debug_rows)

    group_seconds_total = sum(float(row.get("group_seconds", 0) or 0) for row in debug_rows)
    ocr_seconds_total = sum(float(row.get("ocr_seconds", 0) or 0) for row in debug_rows)
    catalog_seconds_total = sum(float(row.get("catalog_match_seconds", 0) or 0) for row in debug_rows)
    reference_seconds_total = sum(float(row.get("reference_match_seconds", 0) or 0) for row in debug_rows)

    slowest_group = ""
    slowest_group_seconds = 0.0
    slowest_group_processed = 0
    slowest_group_early_stopped = False
    for row in debug_rows:
        group_id = str(row.get("group_id", "")).strip()
        seconds = float(row.get("group_seconds", 0) or 0)
        if group_id and seconds >= slowest_group_seconds:
            slowest_group_seconds = seconds
            slowest_group = group_id
            slowest_group_processed = _safe_int(row.get("processed_views"))
            slowest_group_early_stopped = _safe_bool(row.get("early_stopped"))

    reference_counts = {
        "high": 0,
        "medium": 0,
        "low": 0,
        "none": 0,
    }
    enriched_groups_count = 0
    for row in reference_rows:
        confidence = str(row.get("confidence", "")).strip().lower()
        if confidence in reference_counts:
            reference_counts[confidence] += 1
        enriched_fields = _load_json(row.get("enriched_fields"))
        if enriched_fields:
            enriched_groups_count += 1

    catalog_counts = {
        "high": 0,
        "conflict": 0,
        "low": 0,
        "none": 0,
    }
    catalog_conflict_resolved_count = 0
    for row in catalog_rows:
        confidence = str(row.get("confidence", "")).strip().lower()
        if confidence in catalog_counts:
            catalog_counts[confidence] += 1
        if _safe_bool(row.get("conflict_resolved")):
            catalog_conflict_resolved_count += 1

    groups_with_empty_barcode = []
    groups_with_empty_product_name = []
    groups_with_empty_qr = []
    problematic_groups = set()

    group_rows_by_id = {row.get("filename", ""): row for row in group_rows if row.get("filename")}

    for group_id in sorted(group_ids):
        row = group_rows_by_id.get(group_id, {})
        product_name = row.get("product_name", "")
        price_card = row.get("price_card", "")
        discount_amount = row.get("discount_amount", "")
        color = str(row.get("color", "") or "").strip().lower()
        barcode = row.get("barcode", "")
        qr_code = row.get("qr_code_barcode", "")

        if _is_empty(barcode):
            groups_with_empty_barcode.append(group_id)
        if _is_empty(qr_code):
            groups_with_empty_qr.append(group_id)
        if _is_empty(product_name) or _is_noisy_product_name(product_name):
            groups_with_empty_product_name.append(group_id)

        confidence = reference_confidence_by_group.get(group_id, "")
        if confidence and confidence != "high":
            problematic_groups.add(group_id)
        if _is_empty(product_name) or _is_noisy_product_name(product_name):
            problematic_groups.add(group_id)
        if _is_empty(price_card):
            problematic_groups.add(group_id)
        if color == "red" and _is_empty(discount_amount):
            problematic_groups.add(group_id)
        if _is_empty(barcode) and _is_empty(qr_code):
            problematic_groups.add(group_id)

    for row in debug_rows:
        group_id = row.get("group_id", "")
        if not group_id:
            continue
        if _safe_int(row.get("processed_views")) == _safe_int(row.get("total_views")):
            confidence = str(row.get("reference_confidence", "")).strip().lower()
            if confidence and confidence != "high":
                problematic_groups.add(group_id)

    processed_views_ratio = round(processed_views / total_views, 3) if total_views else 0.0

    timing_summary: dict[str, Any] = {}
    timing_available = bool(timing_rows)
    if timing_available:
        stage_totals: dict[str, float] = {}
        group_totals: dict[str, float] = {}
        for row in timing_rows:
            stage = str(row.get("stage", "")).strip()
            seconds = float(row.get("seconds", 0) or 0)
            stage_totals[stage] = stage_totals.get(stage, 0.0) + seconds
            if stage == "group_total":
                group_id = str(row.get("group_id", "")).strip()
                if group_id:
                    group_totals[group_id] = group_totals.get(group_id, 0.0) + seconds

        total_seconds = stage_totals.get("total_run", 0.0)
        if not total_seconds:
            total_seconds = stage_totals.get("grouped_processing", 0.0)
        if not total_seconds:
            total_seconds = sum(group_totals.values())

        slowest_group = ""
        slowest_group_seconds = 0.0
        if group_totals:
            slowest_group, slowest_group_seconds = max(group_totals.items(), key=lambda item: item[1])

        avg_seconds_per_group = (total_seconds / len(group_totals)) if group_totals else 0.0
        avg_seconds_per_processed_view = (total_seconds / processed_views) if processed_views else 0.0

        timing_summary = {
            "total_seconds": round(total_seconds, 3),
            "avg_seconds_per_group": round(avg_seconds_per_group, 3),
            "avg_seconds_per_processed_view": round(avg_seconds_per_processed_view, 4),
            "slowest_group": slowest_group,
            "slowest_group_seconds": round(slowest_group_seconds, 3),
            "catalog_load_seconds": round(stage_totals.get("load_product_catalog", 0.0), 3),
            "reference_load_seconds": round(stage_totals.get("load_reference", 0.0), 3),
            "group_processing_seconds": round(stage_totals.get("grouped_processing", 0.0), 3),
        }

    avg_group_seconds = (group_seconds_total / len(debug_rows)) if debug_rows else 0.0
    avg_ocr_seconds_per_processed_view = (ocr_seconds_total / processed_views) if processed_views else 0.0
    avg_catalog_match_seconds_per_group = (catalog_seconds_total / len(debug_rows)) if debug_rows else 0.0
    avg_reference_match_seconds_per_group = (reference_seconds_total / len(debug_rows)) if debug_rows else 0.0

    summary = {
        "total_groups": len(group_ids),
        "rows_in_output": len(group_rows),
        "reference_high_count": reference_counts["high"],
        "reference_medium_count": reference_counts["medium"],
        "reference_low_count": reference_counts["low"],
        "reference_none_count": reference_counts["none"],
        "catalog_high_count": catalog_counts["high"],
        "catalog_conflict_count": catalog_counts["conflict"],
        "catalog_conflict_resolved_count": catalog_conflict_resolved_count,
        "catalog_low_count": catalog_counts["low"],
        "catalog_none_count": catalog_counts["none"],
        "enriched_groups_count": enriched_groups_count,
        "total_views": total_views,
        "processed_views": processed_views,
        "skipped_views": skipped_views,
        "processed_views_ratio": processed_views_ratio,
        "early_stopped_count": early_stopped_count,
        "ocr_cache_hits": ocr_cache_hits,
        "ocr_cache_misses": ocr_cache_misses,
        "groups_with_empty_barcode": len(groups_with_empty_barcode),
        "groups_with_empty_product_name": len(groups_with_empty_product_name),
        "groups_with_empty_qr": len(groups_with_empty_qr),
        "problematic_groups": " | ".join(sorted(problematic_groups)) if problematic_groups else "none",
        "avg_group_seconds": round(avg_group_seconds, 3),
        "avg_ocr_seconds_per_processed_view": round(avg_ocr_seconds_per_processed_view, 4),
        "avg_catalog_match_seconds_per_group": round(avg_catalog_match_seconds_per_group, 4),
        "avg_reference_match_seconds_per_group": round(avg_reference_match_seconds_per_group, 4),
        "slowest_group": slowest_group,
        "slowest_group_seconds": round(slowest_group_seconds, 3),
        "slowest_group_processed_views": slowest_group_processed,
        "slowest_group_early_stopped": slowest_group_early_stopped,
    }
    summary.update(timing_summary)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with SUMMARY_CSV_PATH.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    summary_lines = [
        "Pipeline Summary",
        "================",
        f"Total groups: {summary['total_groups']}",
        f"Rows in output: {summary['rows_in_output']}",
        f"Reference high: {summary['reference_high_count']}/{summary['total_groups']}",
        f"Reference medium: {summary['reference_medium_count']}",
        f"Reference low: {summary['reference_low_count']}",
        f"Reference none: {summary['reference_none_count']}",
        f"Catalog high: {summary['catalog_high_count']}",
        f"Catalog conflict: {summary['catalog_conflict_count']}",
        f"Catalog conflict resolved: {summary['catalog_conflict_resolved_count']}",
        f"Catalog low: {summary['catalog_low_count']}",
        f"Catalog none: {summary['catalog_none_count']}",
        f"Enriched groups: {summary['enriched_groups_count']}",
        f"Views processed: {summary['processed_views']} / {summary['total_views']} ({summary['processed_views_ratio']})",
        f"Early stopped: {summary['early_stopped_count']}",
        f"OCR cache hits: {summary['ocr_cache_hits']}",
        f"OCR cache misses: {summary['ocr_cache_misses']}",
        f"Problematic groups: {summary['problematic_groups']}",
    ]
    if timing_available:
        summary_lines.extend([
            "",
            "Timing:",
            f"- total_seconds: {summary.get('total_seconds', 0.0)}",
            f"- avg_seconds_per_group: {summary.get('avg_seconds_per_group', 0.0)}",
            f"- avg_seconds_per_processed_view: {summary.get('avg_seconds_per_processed_view', 0.0)}",
            f"- slowest_group: {summary.get('slowest_group', '')}",
            f"- slowest_group_seconds: {summary.get('slowest_group_seconds', 0.0)}",
            f"- slowest_group_processed_views: {summary.get('slowest_group_processed_views', 0)}",
            f"- slowest_group_early_stopped: {summary.get('slowest_group_early_stopped', False)}",
            f"- catalog_load_seconds: {summary.get('catalog_load_seconds', 0.0)}",
            f"- reference_load_seconds: {summary.get('reference_load_seconds', 0.0)}",
            f"- group_processing_seconds: {summary.get('group_processing_seconds', 0.0)}",
            f"- avg_group_seconds: {summary.get('avg_group_seconds', 0.0)}",
            f"- avg_ocr_seconds_per_processed_view: {summary.get('avg_ocr_seconds_per_processed_view', 0.0)}",
            f"- avg_catalog_match_seconds_per_group: {summary.get('avg_catalog_match_seconds_per_group', 0.0)}",
            f"- avg_reference_match_seconds_per_group: {summary.get('avg_reference_match_seconds_per_group', 0.0)}",
        ])
    else:
        summary_lines.extend(["", "Timing: timing not available"])
    SUMMARY_TXT_PATH.write_text("\n".join(summary_lines), encoding="utf-8-sig")

    print(f"Saved pipeline summary: {SUMMARY_CSV_PATH}")
    print(f"Saved pipeline summary: {SUMMARY_TXT_PATH}")
    return summary


if __name__ == "__main__":
    build_pipeline_summary()

"""Simple timing utilities for pipeline benchmarking."""

from __future__ import annotations

import csv
import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any


@dataclass
class TimerRecord:
    name: str
    seconds: float
    metadata: dict[str, Any] = field(default_factory=dict)


class PipelineTimer:
    def __init__(self) -> None:
        self.records: list[TimerRecord] = []

    @contextmanager
    def section(self, name: str, **metadata: Any):
        start = perf_counter()
        holder: dict[str, float] = {"seconds": 0.0}
        try:
            yield holder
        finally:
            seconds = perf_counter() - start
            holder["seconds"] = seconds
            self.add_record(name, seconds, **metadata)

    def add_record(self, name: str, seconds: float, **metadata: Any) -> None:
        self.records.append(TimerRecord(name=name, seconds=seconds, metadata=dict(metadata)))

    def summary(self) -> dict[str, Any]:
        stage_totals: dict[str, float] = {}
        group_totals: dict[str, float] = {}
        for record in self.records:
            stage_totals[record.name] = stage_totals.get(record.name, 0.0) + record.seconds
            group_id = record.metadata.get("group_id")
            if record.name == "group_total" and group_id:
                group_totals[str(group_id)] = group_totals.get(str(group_id), 0.0) + record.seconds

        total_seconds = stage_totals.get("total_run", 0.0)
        if not total_seconds:
            total_seconds = sum(group_totals.values()) or sum(stage_totals.values())

        slowest_group = ""
        slowest_group_seconds = 0.0
        if group_totals:
            slowest_group, slowest_group_seconds = max(group_totals.items(), key=lambda item: item[1])

        return {
            "total_seconds": round(total_seconds, 3),
            "stage_totals": stage_totals,
            "group_totals": group_totals,
            "slowest_group": slowest_group,
            "slowest_group_seconds": round(slowest_group_seconds, 3),
        }

    def save_csv(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=["stage", "seconds", "group_id", "extra"])
            writer.writeheader()
            for record in self.records:
                group_id = record.metadata.get("group_id", "")
                extra = dict(record.metadata)
                extra.pop("group_id", None)
                writer.writerow({
                    "stage": record.name,
                    "seconds": round(record.seconds, 6),
                    "group_id": group_id,
                    "extra": json.dumps(extra, ensure_ascii=False),
                })

    def save_txt(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        summary = self.summary()
        stage_totals = summary.get("stage_totals", {})
        group_totals = summary.get("group_totals", {})

        group_details: list[tuple[str, dict[str, Any]]] = []
        for record in self.records:
            if record.name != "group_total":
                continue
            group_id = str(record.metadata.get("group_id", "")).strip()
            if not group_id:
                continue
            group_details.append((group_id, record.metadata))

        lines = [
            "Timing Report",
            "=============",
            f"Total run: {summary.get('total_seconds', 0.0):.2f} sec",
            "",
            "Stages:",
        ]
        for name in sorted(stage_totals.keys()):
            lines.append(f"- {name}: {stage_totals[name]:.2f} sec")

        if group_totals:
            lines.append("")
            lines.append("Groups:")
            details_by_group = {group_id: metadata for group_id, metadata in group_details}
            for group_id, seconds in sorted(group_totals.items(), key=lambda item: item[1], reverse=True):
                metadata = details_by_group.get(group_id, {})
                total_views = metadata.get("total_views", "")
                processed_views = metadata.get("processed_views", "")
                early_stopped = metadata.get("early_stopped", "")
                reference_confidence = metadata.get("reference_confidence", "")
                catalog_confidence = metadata.get("catalog_confidence", "")
                ocr_seconds = metadata.get("ocr_seconds", "")
                lines.append(
                    f"- {group_id} | {seconds:.2f}s | {processed_views}/{total_views} | {early_stopped} | "
                    f"{reference_confidence} | {catalog_confidence} | {ocr_seconds}s"
                )

        target.write_text("\n".join(lines), encoding="utf-8-sig")

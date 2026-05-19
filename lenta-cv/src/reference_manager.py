"""Select organizer reference CSV from grouped input metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_DEPARTMENTS = {
    "wine/25_2-10",
    "wine/25_12-20",
    "wine/26_12-20",
    "gastronomy/43_15",
    "dairy/49_5",
    "unknown",
}


@dataclass
class ReferenceSelection:
    enabled: bool
    reference_path: str
    department: str
    base_department: str
    reference_key: str
    mode: str
    reason: str


def resolve_project_path(path: str | Path) -> Path:
    result = Path(path)
    if result.is_absolute():
        return result
    return PROJECT_ROOT / result


def read_input_department(input_root: str | Path) -> dict:
    """Read department metadata from input_root/name.json."""
    root = resolve_project_path(input_root)
    metadata_path = root / "name.json"
    if not metadata_path.exists():
        return {
            "department": "unknown",
            "reason": "name_json_not_found",
            "path": str(metadata_path),
        }

    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        return {
            "department": "unknown",
            "reason": f"name_json_invalid: {error}",
            "path": str(metadata_path),
        }
    except OSError as error:
        return {
            "department": "unknown",
            "reason": f"name_json_read_error: {error}",
            "path": str(metadata_path),
        }

    department = data.get("department") if isinstance(data, dict) else None
    if not isinstance(department, str) or not department.strip():
        return {
            "department": "unknown",
            "reason": "department_missing_or_invalid",
            "path": str(metadata_path),
        }

    return {
        "department": department.strip(),
        "reason": "department_read",
        "path": str(metadata_path),
    }


def parse_department_key(department_value: str) -> tuple[str, str]:
    """Split department value into base department and reference key."""
    department = str(department_value or "").strip()
    if not department or department == "unknown":
        return "unknown", ""
    if "/" not in department:
        return department, ""
    base_department, reference_key = department.split("/", 1)
    return base_department.strip() or "unknown", reference_key.strip()


def select_reference_by_department(
    input_root: str | Path,
    reference_dir: str | Path = "data/reference/references",
    reference_mode: str = "auto",
    forced_reference: str | Path | None = None,
) -> ReferenceSelection:
    """Select reference CSV by input department metadata."""
    mode = str(reference_mode or "auto").strip().lower()
    if mode not in {"auto", "off", "forced"}:
        mode = "auto"

    if mode == "off":
        return ReferenceSelection(
            enabled=False,
            reference_path="",
            department="unknown",
            base_department="unknown",
            reference_key="",
            mode="off",
            reason="reference_mode_off",
        )

    if mode == "forced":
        if forced_reference is None:
            return ReferenceSelection(
                enabled=False,
                reference_path="",
                department="unknown",
                base_department="unknown",
                reference_key="",
                mode="forced",
                reason="forced_reference_missing",
            )
        reference_path = resolve_project_path(forced_reference)
        if not reference_path.exists():
            return ReferenceSelection(
                enabled=False,
                reference_path=str(reference_path),
                department="unknown",
                base_department="unknown",
                reference_key=reference_path.stem,
                mode="forced",
                reason="forced_reference_file_not_found",
            )
        return ReferenceSelection(
            enabled=True,
            reference_path=str(reference_path),
            department="forced",
            base_department="forced",
            reference_key=reference_path.stem,
            mode="forced",
            reason="forced_reference_selected",
        )

    metadata = read_input_department(input_root)
    department = str(metadata.get("department", "unknown"))
    if department not in SUPPORTED_DEPARTMENTS:
        base_department, reference_key = parse_department_key(department)
        return ReferenceSelection(
            enabled=False,
            reference_path="",
            department=department,
            base_department=base_department,
            reference_key=reference_key,
            mode="auto",
            reason="unsupported_department",
        )
    base_department, reference_key = parse_department_key(department)
    if department == "unknown" or not reference_key:
        return ReferenceSelection(
            enabled=False,
            reference_path="",
            department=department,
            base_department=base_department,
            reference_key=reference_key,
            mode="auto",
            reason="department_unknown" if department == "unknown" else "reference_key_missing",
        )

    reference_path = resolve_project_path(reference_dir) / f"{reference_key}.csv"
    if not reference_path.exists():
        return ReferenceSelection(
            enabled=False,
            reference_path=str(reference_path),
            department=department,
            base_department=base_department,
            reference_key=reference_key,
            mode="auto",
            reason="reference_file_not_found",
        )

    return ReferenceSelection(
        enabled=True,
        reference_path=str(reference_path),
        department=department,
        base_department=base_department,
        reference_key=reference_key,
        mode="auto",
        reason="reference_selected_by_department",
    )


if __name__ == "__main__":
    selection = select_reference_by_department("input/TestFull")
    print(selection)

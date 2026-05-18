"""Small JSON cache for OCR results during grouped development runs."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = PROJECT_ROOT / "outputs" / "ocr_cache"
OCR_CACHE_VERSION = "v1"
_STATS = {"hits": 0, "misses": 0}


def _resolve_path(path: str | Path) -> Path:
    result = Path(path)
    if result.is_absolute():
        return result
    return PROJECT_ROOT / result


def _cache_path(key: str, cache_dir: str | Path = DEFAULT_CACHE_DIR) -> Path:
    directory = _resolve_path(cache_dir)
    return directory / f"{key}.json"


def get_ocr_cache_key(
    image_path: str | Path,
    ocr_profile: str,
    settings_version: str = OCR_CACHE_VERSION,
) -> str:
    """Build a cache key from the file identity and OCR settings."""
    path = _resolve_path(image_path)
    stat = path.stat()
    payload = "|".join((
        str(path.resolve()),
        str(stat.st_size),
        str(stat.st_mtime_ns),
        str(ocr_profile),
        str(settings_version),
    ))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _json_safe(value: Any) -> Any:
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if hasattr(value, "tolist"):
        return _json_safe(value.tolist())
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def load_cached_ocr(image_path: str | Path, ocr_profile: str) -> list[dict] | None:
    """Load cached OCR results or return None on miss/corruption."""
    try:
        key = get_ocr_cache_key(image_path, ocr_profile)
    except OSError:
        _STATS["misses"] += 1
        return None

    path = _cache_path(key)
    if not path.exists():
        _STATS["misses"] += 1
        return None

    try:
        with path.open("r", encoding="utf-8") as cache_file:
            payload = json.load(cache_file)
    except (OSError, json.JSONDecodeError):
        _STATS["misses"] += 1
        return None

    if payload.get("cache_version") != OCR_CACHE_VERSION:
        _STATS["misses"] += 1
        return None
    results = payload.get("results")
    if not isinstance(results, list):
        _STATS["misses"] += 1
        return None

    _STATS["hits"] += 1
    return results


def save_cached_ocr(image_path: str | Path, ocr_profile: str, ocr_results: list[dict]) -> None:
    """Save OCR results to the JSON cache."""
    try:
        key = get_ocr_cache_key(image_path, ocr_profile)
    except OSError:
        return

    path = _cache_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "image_path": str(_resolve_path(image_path)),
        "ocr_profile": ocr_profile,
        "cache_version": OCR_CACHE_VERSION,
        "results": _json_safe(ocr_results),
    }
    with path.open("w", encoding="utf-8") as cache_file:
        json.dump(payload, cache_file, ensure_ascii=False)


def clear_ocr_cache(cache_dir: str | Path = DEFAULT_CACHE_DIR) -> None:
    """Remove all cached OCR JSON files."""
    directory = _resolve_path(cache_dir)
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)
    reset_ocr_cache_stats()


def get_ocr_cache_stats() -> dict[str, int]:
    """Return cache hit/miss counters for the current process."""
    return dict(_STATS)


def reset_ocr_cache_stats() -> None:
    """Reset cache hit/miss counters."""
    _STATS["hits"] = 0
    _STATS["misses"] = 0


if __name__ == "__main__":
    print(DEFAULT_CACHE_DIR)

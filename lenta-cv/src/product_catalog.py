"""Fast product-name lookup against organizer catalog CSV."""

from __future__ import annotations

import csv
import hashlib
import json
import pickle
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from src.schema import normalize_result_row
from src.text_normalization import normalize_product_tokens, normalize_text
from src.utils.barcode import is_valid_ean13, normalize_barcode


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_CATALOG_CACHE_VERSION = "v1"
PRODUCT_CATALOG_NORMALIZATION_VERSION = "v1"
DEFAULT_PRODUCT_CATALOG_CACHE_DIR = "outputs/product_catalog_cache"
COMMON_TOKENS = {
    "вино",
    "франция",
    "сух",
    "сухое",
    "бел",
    "белое",
    "кр",
    "красн",
    "сорт",
    "ордин",
    "орд",
    "0.75l",
    "нет",
}

DISTINGUISHING_STOP_TOKENS = COMMON_TOKENS | {
    "pure",
    "altitude",
    "haut",
    "marin",
}


@dataclass
class ProductCatalogItem:
    fullname: str
    code: str
    normalized_name: str
    tokens: set[str]


@dataclass
class ProductCatalogMatch:
    matched: bool
    confidence: str
    score: float
    second_score: float
    margin: float
    best_item: ProductCatalogItem | None
    top_candidates: list[dict]
    distinguishing_tokens: list[str]
    reasons: list[str]
    warnings: list[str]
    code_is_unique_for_fullname: bool = False
    conflict_resolution: dict[str, Any] | None = None


def resolve_project_path(path: str | Path) -> Path:
    result = Path(path)
    if result.is_absolute():
        return result
    return PROJECT_ROOT / result


def _read_catalog_rows(path: Path) -> list[dict[str, Any]]:
    for encoding in ("cp1251", "utf-8-sig"):
        try:
            with path.open("r", newline="", encoding=encoding) as catalog_file:
                reader = csv.DictReader(catalog_file, delimiter=";")
                return list(reader)
        except UnicodeDecodeError:
            continue
    with path.open("r", newline="", encoding="utf-8-sig", errors="replace") as catalog_file:
        reader = csv.DictReader(catalog_file, delimiter=";")
        return list(reader)


def load_product_catalog(path: str | Path) -> list[ProductCatalogItem]:
    """Load db_hack.csv-like product catalog rows."""
    catalog_path = resolve_project_path(path)
    rows = _read_catalog_rows(catalog_path)
    items: list[ProductCatalogItem] = []
    for row in rows:
        fullname = str(row.get("fullname", "") or "").strip()
        if not fullname:
            continue
        code = normalize_barcode(str(row.get("code", "") or ""))
        items.append(ProductCatalogItem(
            fullname=fullname,
            code=code,
            normalized_name=normalize_text(fullname),
            tokens=normalize_product_tokens(fullname),
        ))
    return items


def _build_product_catalog_cache_metadata(
    csv_path: str | Path,
    cache_version: str = PRODUCT_CATALOG_CACHE_VERSION,
) -> dict[str, Any]:
    source_path = resolve_project_path(csv_path).resolve()
    stat = source_path.stat()
    return {
        "source_path": str(source_path),
        "source_size": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
        "cache_version": cache_version,
        "normalization_version": PRODUCT_CATALOG_NORMALIZATION_VERSION,
    }


def get_product_catalog_cache_key(
    csv_path: str | Path,
    cache_version: str = PRODUCT_CATALOG_CACHE_VERSION,
) -> str:
    """Return a stable cache key for the catalog source file and parser version."""
    metadata = _build_product_catalog_cache_metadata(csv_path, cache_version=cache_version)
    payload = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_product_catalog_cache_path(
    csv_path: str | Path,
    cache_dir: str | Path = DEFAULT_PRODUCT_CATALOG_CACHE_DIR,
) -> Path:
    """Return the pickle cache path for a product catalog CSV."""
    directory = resolve_project_path(cache_dir)
    cache_key = get_product_catalog_cache_key(csv_path)
    return directory / f"{cache_key}.pkl"


def save_product_catalog_index_cache(
    index: "ProductCatalogIndex",
    cache_path: str | Path,
    metadata: dict,
) -> None:
    """Persist a locally built ProductCatalogIndex to disk."""
    path = resolve_project_path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": metadata,
        "index": index,
    }
    with path.open("wb") as cache_file:
        pickle.dump(payload, cache_file, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"[ProductCatalog] Saved index cache: {path}")


def load_product_catalog_index_cache(
    cache_path: str | Path,
    expected_metadata: dict,
) -> "ProductCatalogIndex | None":
    """Load a cached ProductCatalogIndex if metadata still matches."""
    path = resolve_project_path(cache_path)
    if not path.exists():
        return None
    try:
        with path.open("rb") as cache_file:
            payload = pickle.load(cache_file)
    except Exception as error:
        print(f"[ProductCatalog] Cache corrupt, ignoring: {path} ({error})")
        try:
            path.unlink()
        except OSError:
            pass
        return None

    metadata = payload.get("metadata") if isinstance(payload, dict) else None
    if metadata != expected_metadata:
        print("[ProductCatalog] Cache invalid: source file changed")
        return None

    index = payload.get("index") if isinstance(payload, dict) else None
    if not isinstance(index, ProductCatalogIndex):
        print(f"[ProductCatalog] Cache invalid: unexpected payload in {path}")
        return None
    print(f"[ProductCatalog] Loading catalog index from cache: {path}")
    return index


def load_product_catalog_index(
    csv_path: str | Path,
    use_cache: bool = True,
    rebuild_cache: bool = False,
    cache_dir: str | Path = DEFAULT_PRODUCT_CATALOG_CACHE_DIR,
) -> "ProductCatalogIndex":
    """Load ProductCatalogIndex from persistent cache or build it from CSV."""
    source_path = resolve_project_path(csv_path)
    expected_metadata = _build_product_catalog_cache_metadata(source_path)
    cache_path = get_product_catalog_cache_path(source_path, cache_dir=cache_dir)

    if not use_cache:
        print("[ProductCatalog] Cache disabled")
    elif not rebuild_cache:
        cached = load_product_catalog_index_cache(cache_path, expected_metadata)
        if cached is not None:
            print(f"[ProductCatalog] Loaded {len(cached.items)} items")
            return cached
        print(f"[ProductCatalog] Cache miss: building index from {source_path}")
    else:
        print(f"[ProductCatalog] Rebuilding catalog index cache from {source_path}")

    print(f"[ProductCatalog] Building index from CSV: {source_path}")
    items = load_product_catalog(source_path)
    print(f"[ProductCatalog] Loaded {len(items)} items")
    index = ProductCatalogIndex(items)

    if use_cache:
        save_product_catalog_index_cache(index, cache_path, expected_metadata)

    return index


def _strong_tokens(tokens: set[str]) -> set[str]:
    return {
        token for token in tokens
        if len(token) >= 4
        and token not in COMMON_TOKENS
        and any(char.isalnum() for char in token)
    }


def _looks_like_volume(token: str) -> bool:
    return token in {"0.75l", "075l", "0.75л", "075л"}


def score_catalog_item(
    query_tokens: set[str],
    query_text: str,
    item: ProductCatalogItem,
) -> tuple[float, list[str]]:
    """Score one catalog item against OCR query tokens."""
    score = 0.0
    reasons: list[str] = []
    item_tokens = item.tokens
    overlap = query_tokens & item_tokens
    if overlap:
        token_score = min(len(overlap) * 8, 50)
        score += token_score
        reasons.append(f"exact token overlap {sorted(overlap)} +{token_score}")

    query_strong = _strong_tokens(query_tokens)
    item_strong = _strong_tokens(item_tokens)
    strong_overlap = query_strong & item_strong
    if len(strong_overlap) >= 2:
        score += 10
        reasons.append("2+ strong tokens +10")

    for query_token in query_strong:
        if query_token in item_tokens:
            continue
        best_ratio = max(
            (SequenceMatcher(None, query_token, item_token).ratio() for item_token in item_strong),
            default=0.0,
        )
        if best_ratio >= 0.82:
            score += 5
            reasons.append(f"similar token {query_token} +5")

    latin_overlap = {
        token for token in strong_overlap
        if len(token) >= 4 and re.search(r"[a-z]", token, re.IGNORECASE)
    }
    if latin_overlap:
        score += 15
        reasons.append(f"brand/latin token {sorted(latin_overlap)} +15")

    if any(_looks_like_volume(token) for token in overlap):
        score += 5
        reasons.append("volume token +5")

    if len(strong_overlap) == 1 and len(overlap) <= 1:
        score -= 10
        reasons.append("single weak match -10")
    if overlap and overlap <= COMMON_TOKENS:
        score -= 15
        reasons.append("only common tokens -15")

    return round(score, 3), reasons


def get_distinguishing_tokens(top_items: list[ProductCatalogItem]) -> list[str]:
    """Return useful tokens that separate top catalog candidates."""
    token_counts: Counter[str] = Counter()
    for item in top_items:
        token_counts.update(_strong_tokens(item.tokens))
    distinguishing = [
        token for token, count in token_counts.items()
        if token not in COMMON_TOKENS and 0 < count < len(top_items)
    ]
    return sorted(distinguishing, key=lambda token: (token_counts[token], token))[:10]


def _match_from_top_candidate(candidate: dict, items: list[ProductCatalogItem]) -> ProductCatalogItem | None:
    fullname = str(candidate.get("fullname", ""))
    code = str(candidate.get("code", ""))
    for item in items:
        if item.fullname == fullname and item.code == code:
            return item
    return None


def _clone_match_with_resolution(
    current_match: ProductCatalogMatch,
    *,
    confidence: str,
    score_bonus: float,
    matched_tokens: list[str],
    reason: str,
    warning: str | None = None,
) -> ProductCatalogMatch:
    score = round(current_match.score + score_bonus, 3)
    margin = max(round(score - current_match.second_score, 3), current_match.margin)
    warnings = list(current_match.warnings)
    if warning:
        warnings.append(warning)
    reasons = list(current_match.reasons)
    reasons.append(reason)
    return ProductCatalogMatch(
        matched=confidence not in {"none", "conflict"},
        confidence=confidence,
        score=score,
        second_score=current_match.second_score,
        margin=margin,
        best_item=current_match.best_item,
        top_candidates=current_match.top_candidates,
        distinguishing_tokens=current_match.distinguishing_tokens,
        reasons=reasons,
        warnings=warnings,
        code_is_unique_for_fullname=current_match.code_is_unique_for_fullname,
        conflict_resolution={
            "resolved": confidence != "conflict",
            "matched_tokens": matched_tokens,
            "reason": reason,
        },
    )


def resolve_catalog_conflict_by_tokens(
    query_texts: list[str],
    top_items: list[ProductCatalogItem],
    current_match: ProductCatalogMatch,
) -> ProductCatalogMatch:
    """Promote a catalog conflict when OCR contains tokens unique to top-1."""
    if current_match.confidence != "conflict" or current_match.best_item is None:
        return current_match

    unique_items: list[ProductCatalogItem] = []
    seen_names: set[str] = set()
    for item in top_items:
        key = item.normalized_name
        if key in seen_names:
            continue
        seen_names.add(key)
        unique_items.append(item)
    items = unique_items[:5]
    if len(items) < 2:
        return current_match

    query_tokens: set[str] = set()
    for text in query_texts:
        query_tokens.update(normalize_product_tokens(text))
    if not query_tokens:
        return current_match

    token_counts: Counter[str] = Counter()
    for item in items:
        token_counts.update(_strong_tokens(item.tokens))

    top_item = current_match.best_item
    top_unique_tokens = {
        token for token in _strong_tokens(top_item.tokens)
        if token not in DISTINGUISHING_STOP_TOKENS and token_counts[token] <= max(1, len(items) // 2)
    }
    matched_top_unique = sorted(top_unique_tokens & query_tokens)

    competitor_matches: dict[str, list[str]] = {}
    for item in items[1:]:
        competitor_unique = {
            token for token in _strong_tokens(item.tokens)
            if token not in DISTINGUISHING_STOP_TOKENS and token_counts[token] <= max(1, len(items) // 2)
        }
        matched = sorted(competitor_unique & query_tokens)
        if matched:
            competitor_matches[item.fullname] = matched

    if matched_top_unique and competitor_matches:
        return _clone_match_with_resolution(
            current_match,
            confidence="conflict",
            score_bonus=0.0,
            matched_tokens=matched_top_unique,
            reason="distinguishing tokens found for multiple catalog candidates",
            warning=f"competing distinguishing tokens: {competitor_matches}",
        )

    if len(matched_top_unique) >= 2:
        return _clone_match_with_resolution(
            current_match,
            confidence="high",
            score_bonus=20.0,
            matched_tokens=matched_top_unique,
            reason=f"resolved conflict by 2+ top-1 distinguishing tokens: {matched_top_unique}",
        )

    if matched_top_unique:
        token = matched_top_unique[0]
        confidence = "high" if len(token) >= 5 else "medium"
        return _clone_match_with_resolution(
            current_match,
            confidence=confidence,
            score_bonus=15.0 if confidence == "high" else 8.0,
            matched_tokens=matched_top_unique,
            reason=f"resolved conflict by top-1 distinguishing token: {token}",
        )

    resolution = {
        "resolved": False,
        "matched_tokens": [],
        "reason": "no top-1 distinguishing token found in OCR product names",
    }
    return ProductCatalogMatch(
        matched=current_match.matched,
        confidence=current_match.confidence,
        score=current_match.score,
        second_score=current_match.second_score,
        margin=current_match.margin,
        best_item=current_match.best_item,
        top_candidates=current_match.top_candidates,
        distinguishing_tokens=current_match.distinguishing_tokens,
        reasons=current_match.reasons,
        warnings=current_match.warnings,
        code_is_unique_for_fullname=current_match.code_is_unique_for_fullname,
        conflict_resolution=resolution,
    )


def _candidate_dict(item: ProductCatalogItem, score: float, reasons: list[str], query_tokens: set[str]) -> dict:
    return {
        "fullname": item.fullname,
        "code": item.code,
        "score": round(score, 3),
        "matched_tokens": sorted(query_tokens & item.tokens),
        "reasons": reasons,
    }


class ProductCatalogIndex:
    """Inverted-index search over a large product catalog."""

    def __init__(self, items: list[ProductCatalogItem]):
        self.items = items
        self.inverted_index: dict[str, set[int]] = defaultdict(set)
        self.fullname_codes: dict[str, set[str]] = defaultdict(set)
        self.items_by_identity: dict[tuple[str, str], ProductCatalogItem] = {}
        for item_id, item in enumerate(items):
            for token in item.tokens:
                self.inverted_index[token].add(item_id)
            if item.code:
                self.fullname_codes[item.normalized_name].add(item.code)
            self.items_by_identity[(item.fullname, item.code)] = item

    def top_items_from_candidates(self, candidates: list[dict], limit: int = 5) -> list[ProductCatalogItem]:
        """Resolve serialized top-candidate dicts back to catalog items."""
        items: list[ProductCatalogItem] = []
        for candidate in candidates[:limit]:
            item = self.items_by_identity.get((
                str(candidate.get("fullname", "")),
                str(candidate.get("code", "")),
            ))
            if item is not None:
                items.append(item)
        return items

    def _candidate_ids(self, tokens: set[str]) -> set[int]:
        strong = _strong_tokens(tokens)
        lookup_tokens = sorted(
            strong or tokens,
            key=lambda token: len(self.inverted_index.get(token, ())),
        )
        lookup_tokens = [token for token in lookup_tokens if token in self.inverted_index][:8]
        if not lookup_tokens:
            return set()

        candidate_ids: set[int] = set()
        for token in lookup_tokens[:5]:
            ids = self.inverted_index.get(token, set())
            candidate_ids.update(ids)
            if len(candidate_ids) > 5000:
                break
        return candidate_ids

    def search(self, query_text: str, limit: int = 20) -> ProductCatalogMatch:
        """Search catalog for a noisy OCR product name."""
        query_tokens = normalize_product_tokens(query_text)
        if not query_tokens:
            return ProductCatalogMatch(False, "none", 0.0, 0.0, 0.0, None, [], [], [], ["no query tokens"])

        candidate_ids = self._candidate_ids(query_tokens)
        if not candidate_ids:
            return ProductCatalogMatch(False, "none", 0.0, 0.0, 0.0, None, [], [], [], ["no catalog candidates"])

        scored: list[tuple[float, ProductCatalogItem, list[str]]] = []
        for item_id in candidate_ids:
            item = self.items[item_id]
            score, reasons = score_catalog_item(query_tokens, query_text, item)
            if score > 0:
                scored.append((score, item, reasons))

        if not scored:
            return ProductCatalogMatch(False, "none", 0.0, 0.0, 0.0, None, [], [], [], ["all candidates scored zero"])

        scored.sort(key=lambda candidate: candidate[0], reverse=True)
        best_score, best_item, best_reasons = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0.0
        margin = best_score - second_score
        best_strong_overlap = _strong_tokens(query_tokens) & _strong_tokens(best_item.tokens)

        if best_score >= 45 and margin >= 12 and len(best_strong_overlap) >= 2:
            confidence = "high"
        elif best_score >= 30 and margin >= 8:
            confidence = "medium"
        elif best_score >= 30 and margin < 8:
            confidence = "conflict"
        elif best_score >= 18:
            confidence = "low"
        else:
            confidence = "none"

        top_scored = scored[:max(limit, 5)]
        top_items = [item for _score, item, _reasons in top_scored[:5]]
        distinguishing_tokens = get_distinguishing_tokens(top_items) if confidence == "conflict" else []
        top_candidates = [
            _candidate_dict(item, score, reasons, query_tokens)
            for score, item, reasons in top_scored[:5]
        ]
        normalized_name = best_item.normalized_name
        unique_codes = {code for code in self.fullname_codes.get(normalized_name, set()) if code}

        return ProductCatalogMatch(
            matched=confidence not in {"none", "conflict"},
            confidence=confidence,
            score=round(best_score, 3),
            second_score=round(second_score, 3),
            margin=round(margin, 3),
            best_item=best_item if confidence != "none" else None,
            top_candidates=top_candidates,
            distinguishing_tokens=distinguishing_tokens,
            reasons=best_reasons,
            warnings=[] if confidence != "conflict" else ["catalog match conflict"],
            code_is_unique_for_fullname=len(unique_codes) == 1,
        )


def _is_noisy_product_name(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    allowed = sum(1 for char in text if char.isalnum() or char.isspace() or char in ".,()/-.")
    weird_ratio = 1.0 - allowed / max(len(text), 1)
    return weird_ratio > 0.25 or len(normalize_product_tokens(text)) < 2


def enrich_product_name_from_catalog(
    row: dict,
    match: ProductCatalogMatch,
) -> tuple[dict, dict]:
    """Enrich only product_name and, when unambiguous, barcode from catalog."""
    enriched = normalize_result_row(row)
    changes: dict[str, dict[str, Any]] = {}
    item = match.best_item
    if item is None:
        return enriched, changes

    should_replace_name = (
        match.confidence == "high"
        or (match.confidence == "medium" and _is_noisy_product_name(enriched.get("product_name")))
    )
    if should_replace_name and item.fullname and enriched.get("product_name", "") != item.fullname:
        changes["product_name"] = {
            "old": enriched.get("product_name", ""),
            "new": item.fullname,
            "source": "product_catalog",
            "reason": f"{match.confidence} confidence catalog match",
        }
        enriched["product_name"] = item.fullname

    if (
        match.confidence == "high"
        and not enriched.get("barcode")
        and match.code_is_unique_for_fullname
        and is_valid_ean13(item.code)
    ):
        changes["barcode"] = {
            "old": enriched.get("barcode", ""),
            "new": item.code,
            "source": "product_catalog",
            "reason": "unique EAN-13 code for matched fullname",
        }
        enriched["barcode"] = item.code

    return normalize_result_row(enriched), changes


def catalog_match_to_dict(match: ProductCatalogMatch | None) -> dict[str, Any] | None:
    if match is None:
        return None
    selected = None
    if match.best_item is not None:
        selected = {
            "fullname": match.best_item.fullname,
            "code": match.best_item.code,
        }
    return {
        "matched": match.matched,
        "confidence": match.confidence,
        "score": match.score,
        "second_score": match.second_score,
        "margin": match.margin,
        "selected_fullname": selected["fullname"] if selected else "",
        "selected_code": selected["code"] if selected else "",
        "top_candidates": match.top_candidates,
        "distinguishing_tokens": match.distinguishing_tokens,
        "conflict_resolution": match.conflict_resolution or {
            "resolved": False,
            "matched_tokens": [],
            "reason": "",
        },
        "reasons": match.reasons,
        "warnings": match.warnings,
    }


if __name__ == "__main__":
    print("product catalog module ready")
